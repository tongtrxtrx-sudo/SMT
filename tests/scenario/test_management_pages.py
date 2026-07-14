import os
import sqlite3
import unittest
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from smt_guard.bom import BomDocument, Material, Product
from smt_guard.feedback import FeedbackTone
from smt_guard.operator import OperatorSession
from smt_guard.run import RunStatus
from smt_guard.scan import ProductConfiguration
from smt_guard.sqlite import (
    SqliteAuditRepository,
    SqliteBomRepository,
    SqliteDatabase,
    SqliteMasterDataRepository,
    SqliteProductConfigurationRepository,
    SqliteProductionRunRepository,
)
from smt_guard.ui.audits import AuditLogWidget
from smt_guard.ui.boms import BomManagementWidget
from smt_guard.ui.configurations import ConfigurationManagementWidget
from smt_guard.ui.runs import ProductionRunManagementWidget
from smt_guard.ui.scanning import ScanWidget


class SilentAudio:
    def emit(self, tone: FeedbackTone) -> None:
        del tone


class ManagementPageTests(unittest.TestCase):
    app: QApplication

    @classmethod
    def setUpClass(cls) -> None:
        application = QApplication.instance()
        if application is None:
            cls.app = QApplication([])
        elif isinstance(application, QApplication):
            cls.app = application
        else:
            raise RuntimeError("A non-GUI Qt application already exists")

    def setUp(self) -> None:
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.connection = sqlite3.connect(":memory:")
        self.addCleanup(self.connection.close)
        SqliteDatabase(self.connection).initialize()
        self.session = OperatorSession("OP-UI")
        self.master = SqliteMasterDataRepository(self.connection)
        self.master.add_device("SMT-01", "Machine", "Line A", actor="OP-UI")
        self.master.add_station("SMT-01", "F-01", actor="OP-UI")

    @staticmethod
    def document(material: str) -> BomDocument:
        return BomDocument(
            Product("501000087", "BOM", "Board BOM", "Board", "Main"),
            {material: Material(material, "Part", "1206", "1", "Electronic")},
        )

    def import_bom(self, version: str, material: str) -> None:
        source = self.directory / f"{version}.xlsx"
        source.write_bytes(version.encode())
        SqliteBomRepository(self.connection).import_document(
            self.document(material),
            source,
            version=version,
            operator="OP-UI",
            imported_at=datetime(2026, 7, 14, 9, 0, tzinfo=UTC),
        )

    def test_bom_page_shows_provenance_compares_and_runs_lifecycle(self) -> None:
        self.import_bom("V1", "M-1")
        self.import_bom("V2", "M-2")
        widget = BomManagementWidget(SqliteBomRepository(self.connection), self.session.require)
        self.addCleanup(widget.close)

        self.assertEqual(2, widget.version_table.rowCount())
        self.assertIn("SHA-256", widget.detail_label.text())
        sha_item = widget.version_table.item(0, 4)
        assert sha_item is not None
        self.assertEqual(sha_item.text(), sha_item.toolTip())
        self.assertGreaterEqual(widget.version_table.columnWidth(1), 170)
        widget.compare_button.click()
        self.assertIn("M-2", widget.compare_label.text())

        widget.version_table.selectRow(0)
        widget.publish_button.click()
        widget.activate_button.click()
        widget.obsolete_button.click()
        widget.archive_button.click()
        self.assertIn("已归档", widget.status_label.text())

        widget.activate_button.click()
        self.assertIn("启用前必须先发布 BOM", widget.status_label.text())
        self.assertNotIn("must be published", widget.status_label.text())

    def test_configuration_page_copies_edits_and_releases_new_version(self) -> None:
        repository = SqliteProductConfigurationRepository(self.connection)
        repository.save(
            ProductConfiguration("501000087", "V1", {("SMT-01", "F-01"): "M-1"}),
            actor="OP-UI",
        )
        widget = ConfigurationManagementWidget(repository, self.session.require)
        self.addCleanup(widget.close)
        version_item = widget.configuration_table.item(0, 1)
        assert version_item is not None
        self.assertEqual(version_item.text(), version_item.toolTip())
        self.assertGreaterEqual(widget.configuration_table.columnWidth(1), 170)
        widget.new_version_input.setText("V2")
        widget.copy_button.click()
        self.assertEqual(2, widget.configuration_table.rowCount())

        widget.configuration_table.selectRow(1)
        widget.assignment_table.item(0, 2).setText("M-2")  # type: ignore[union-attr]
        widget.save_draft_button.click()
        widget.publish_button.click()
        widget.activate_button.click()
        self.assertEqual(
            "M-2",
            repository.get("501000087", "V2").required_material("SMT-01", "F-01"),
        )

    def test_run_and_audit_pages_filter_and_show_snapshot_details(self) -> None:
        configurations = SqliteProductConfigurationRepository(self.connection)
        configuration = ProductConfiguration("501000087", "V1", {("SMT-01", "F-01"): "M-1"})
        configurations.save(configuration, actor="OP-UI")
        runs = SqliteProductionRunRepository(self.connection)
        runs.start(
            "RUN-UI",
            configuration,
            operator="OP-UI",
            started_at=datetime(2026, 7, 14, 10, 0, tzinfo=UTC),
        )
        runs.interrupt(
            "RUN-UI",
            operator="OP-UI",
            interrupted_at=datetime(2026, 7, 14, 10, 1, tzinfo=UTC),
            reason="换线",
        )
        run_widget = ProductionRunManagementWidget(runs)
        self.addCleanup(run_widget.close)
        run_widget.status_combo.setCurrentIndex(3)
        run_widget.query_input.setText("RUN-UI")
        run_widget.refresh()

        run_id_item = run_widget.run_table.item(0, 0)
        assert run_id_item is not None
        self.assertEqual("RUN-UI", run_id_item.toolTip())
        self.assertGreaterEqual(run_widget.run_table.columnWidth(0), 220)

        resumed: list[str] = []
        run_widget.resume_requested.connect(resumed.append)
        run_widget.resume_button.click()
        self.assertEqual(["RUN-UI"], resumed)
        self.assertEqual(1, run_widget.station_table.rowCount())
        self.assertIn("OP-UI", run_widget.snapshot_label.text())

        audit_widget = AuditLogWidget(SqliteAuditRepository(self.connection))
        self.addCleanup(audit_widget.close)
        audit_widget.actor_input.setText("OP-UI")
        audit_widget.entity_type_input.setText("PRODUCTION_RUN")
        audit_widget.refresh()
        self.assertEqual(2, audit_widget.audit_table.rowCount())
        first_action = audit_widget.audit_table.item(0, 4)
        assert first_action is not None
        self.assertEqual("INTERRUPT", first_action.text())
        entity_key = audit_widget.audit_table.item(0, 3)
        assert entity_key is not None
        self.assertEqual(entity_key.text(), entity_key.toolTip())
        self.assertGreaterEqual(audit_widget.audit_table.columnWidth(3), 240)
        self.assertEqual(RunStatus.INTERRUPTED, runs.get("RUN-UI").status)

        audit_widget.started_from_input.setText("not-a-time")
        audit_widget.refresh()
        self.assertIn("无效 ISO 时间", audit_widget.status_label.text())

    def test_audit_page_distinguishes_unqueried_zero_and_refreshes_when_activated(self) -> None:
        repository = SqliteAuditRepository(self.connection)
        widget = AuditLogWidget(repository)
        self.addCleanup(widget.close)
        self.assertIn("尚未查询", widget.status_label.text())

        widget.entity_type_input.setText("NO_SUCH_ENTITY")
        widget.show()
        self.app.processEvents()
        self.assertEqual(0, widget.audit_table.rowCount())
        self.assertIn("查询完成：0 条", widget.status_label.text())

        widget.hide()
        widget.entity_type_input.clear()
        self.master.add_device("SMT-02", "Machine 2", "Line B", actor="OP-UI")
        widget.show()
        self.app.processEvents()
        self.assertGreater(widget.audit_table.rowCount(), 0)
        self.assertIn("查询完成：", widget.status_label.text())

    def test_run_refresh_renders_new_first_row_even_when_row_zero_stays_selected(self) -> None:
        configurations = SqliteProductConfigurationRepository(self.connection)
        first_configuration = ProductConfiguration("501000087", "V1", {("SMT-01", "F-01"): "M-1"})
        configurations.save(first_configuration, actor="OP-UI")
        runs = SqliteProductionRunRepository(self.connection)
        runs.start(
            "RUN-OLD",
            first_configuration,
            operator="OP-OLD",
            started_at=datetime(2026, 7, 14, 10, 0, tzinfo=UTC),
        )
        runs.interrupt(
            "RUN-OLD",
            operator="OP-OLD",
            interrupted_at=datetime(2026, 7, 14, 10, 1, tzinfo=UTC),
            reason="换线",
        )
        widget = ProductionRunManagementWidget(runs)
        self.addCleanup(widget.close)
        self.assertTrue(widget.resume_button.isEnabled())
        self.assertIn("OP-OLD", widget.snapshot_label.text())

        second_configuration = ProductConfiguration("501000087", "V2", {("SMT-01", "F-01"): "M-2"})
        configurations.save(second_configuration, actor="OP-NEW")
        runs.start(
            "RUN-NEW",
            second_configuration,
            operator="OP-NEW",
            started_at=datetime(2026, 7, 14, 10, 2, tzinfo=UTC),
        )

        widget.refresh()

        self.assertEqual("RUN-NEW", widget.run_table.item(0, 0).text())  # type: ignore[union-attr]
        self.assertEqual(0, widget.run_table.currentRow())
        self.assertIn("501000087/V2", widget.snapshot_label.text())
        self.assertIn("OP-NEW", widget.snapshot_label.text())
        self.assertFalse(widget.resume_button.isEnabled())
        self.assertTrue(widget.interrupt_button.isEnabled())
        self.assertEqual("M-2", widget.station_table.item(0, 2).text())  # type: ignore[union-attr]

        widget.query_input.setText("NO-SUCH-RUN")
        widget.refresh()

        self.assertEqual(0, widget.run_table.rowCount())
        self.assertEqual(0, widget.station_table.rowCount())
        self.assertFalse(widget.resume_button.isEnabled())
        self.assertFalse(widget.interrupt_button.isEnabled())

    def test_scanner_resumes_and_interrupts_persisted_runs(self) -> None:
        configurations = SqliteProductConfigurationRepository(self.connection)
        configuration = ProductConfiguration("501000087", "V1", {("SMT-01", "F-01"): "M-1"})
        configurations.save(configuration, actor="OP-UI")
        runs = SqliteProductionRunRepository(self.connection)
        widget = ScanWidget(
            configurations,
            runs,
            SilentAudio(),
            clock=lambda: datetime(2026, 7, 14, 11, 0, tzinfo=UTC),
            run_id_factory=lambda: "RUN-RESUME",
            runs=runs,
            operator_provider=self.session.require,
        )
        self.addCleanup(widget.close)

        widget.start_button.click()
        widget.interrupt_active_run("暂停")
        self.assertEqual(RunStatus.INTERRUPTED, runs.get("RUN-RESUME").status)
        widget.resume_run("RUN-RESUME")
        self.assertTrue(widget.scan_input.isEnabled())
        self.assertTrue(widget.submit_button.isEnabled())
        self.assertEqual("OP-UI", runs.get("RUN-RESUME").operator)
        widget.interrupt_run("RUN-RESUME", "人工中断")
        self.assertEqual(RunStatus.INTERRUPTED, runs.get("RUN-RESUME").status)
        self.assertFalse(widget.scan_input.isEnabled())

    def test_management_pages_report_invalid_or_missing_actions(self) -> None:
        bom_widget = BomManagementWidget(SqliteBomRepository(self.connection), self.session.require)
        self.addCleanup(bom_widget.close)
        bom_widget.publish_button.click()
        bom_widget.compare_button.click()
        self.assertIn("请选择", bom_widget.status_label.text())

        config_widget = ConfigurationManagementWidget(
            SqliteProductConfigurationRepository(self.connection), self.session.require
        )
        self.addCleanup(config_widget.close)
        config_widget.copy_button.click()
        config_widget.validate_button.click()
        config_widget.save_draft_button.click()
        self.assertIn("产品配置", config_widget.status_label.text())

        run_widget = ProductionRunManagementWidget(SqliteProductionRunRepository(self.connection))
        self.addCleanup(run_widget.close)
        run_widget.started_from_input.setText("invalid")
        run_widget.refresh()
        self.assertIn("无效 ISO 时间", run_widget.status_label.text())


if __name__ == "__main__":
    unittest.main()
