import os
import sqlite3
import unittest
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDateTimeEdit

from smt_guard.bom import BomDocument, BomVersion, Material, Product
from smt_guard.feedback import FeedbackTone, VoicePrompt
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


class FakeAnnouncementSink:
    def __init__(self) -> None:
        self.prompts: list[VoicePrompt] = []

    def announce(self, prompt: VoicePrompt) -> None:
        self.prompts.append(prompt)


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
        self.clock = lambda: datetime(2026, 7, 16, 12, 0, tzinfo=UTC)

    @staticmethod
    def document(*materials: str) -> BomDocument:
        return BomDocument(
            Product("501000087", "BOM", "Board BOM", "Board", "Main"),
            {
                material: Material(material, "Part", "1206", "1", "Electronic")
                for material in materials
            },
        )

    def import_bom(
        self, version: str, material: str, *additional_materials: str
    ) -> BomVersion:
        source = self.directory / f"{version}.xlsx"
        source.write_bytes(version.encode())
        return SqliteBomRepository(self.connection).import_document(
            self.document(material, *additional_materials),
            source,
            version=version,
            operator="OP-UI",
            imported_at=datetime(2026, 7, 14, 9, 0, tzinfo=UTC),
        )

    def test_bom_page_shows_provenance_compares_and_marks_current_version(self) -> None:
        self.import_bom("V1", "M-1")
        self.import_bom("V2", "M-2")
        repository = SqliteBomRepository(self.connection)
        repository.publish("501000087", "V2", actor="OP-UI")
        repository.activate("501000087", "V2", actor="OP-UI")
        announcer = FakeAnnouncementSink()
        widget = BomManagementWidget(
            repository,
            self.session.require,
            announcer=announcer,
        )
        self.addCleanup(widget.close)
        widget.resize(1180, 700)
        widget.show()
        self.app.processEvents()

        self.assertEqual(2, widget.version_table.rowCount())
        self.assertEqual(
            {"当前版本", "历史版本"},
            {widget.version_table.item(row, 2).text() for row in range(2)},  # type: ignore[union-attr]
        )
        self.assertEqual(
            "版本定位", widget.version_table.horizontalHeaderItem(2).text()  # type: ignore[union-attr]
        )
        self.assertFalse(hasattr(widget, "activate_button"))
        self.assertFalse(hasattr(widget, "disable_button"))
        self.assertIn("SHA-256", widget.detail_label.text())
        self.assertIn("来源：", widget.detail_label.text())
        self.assertIn("by OP-UI", widget.detail_label.text())
        self.assertEqual(5, widget.version_table.columnCount())
        self.assertEqual("物料数", widget.version_table.horizontalHeaderItem(3).text())  # type: ignore[union-attr]
        self.assertGreaterEqual(widget.version_table.columnWidth(1), 150)
        self.assertEqual(
            0,
            widget.version_table.horizontalScrollBar().maximum(),
            msg=(
                f"table={widget.version_table.width()} "
                f"viewport={widget.version_table.viewport().width()} "
                f"columns={[widget.version_table.columnWidth(i) for i in range(5)]}"
            ),
        )
        self.assertEqual(0, widget.material_table.horizontalScrollBar().maximum())
        self.assertEqual(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
            widget.version_table.horizontalScrollBarPolicy(),
        )
        self.assertEqual(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
            widget.material_table.horizontalScrollBarPolicy(),
        )
        widget.compare_button.click()
        self.assertIn("M-2", widget.compare_label.text())
        widget.version_table.selectRow(1)
        self.assertIn("当前 BOM 版本", widget.lifecycle_hint_label.text())
        self.assertEqual([], announcer.prompts)

    def test_configuration_page_copies_edits_and_releases_new_version(self) -> None:
        repository = SqliteProductConfigurationRepository(self.connection)
        boms = SqliteBomRepository(self.connection)
        bom = self.import_bom("BOM-V1", "M-1", "M-2")
        repository.save(
            ProductConfiguration(
                "501000087",
                "V1",
                {("SMT-01", "F-01"): "M-1"},
                bom.id,
            ),
            actor="OP-UI",
        )
        announcer = FakeAnnouncementSink()
        widget = ConfigurationManagementWidget(
            repository,
            self.session.require,
            announcer=announcer,
            bom_repository=boms,
        )
        self.addCleanup(widget.close)
        version_item = widget.configuration_table.item(0, 3)
        assert version_item is not None
        self.assertEqual(version_item.text(), version_item.toolTip())
        self.assertGreaterEqual(widget.configuration_table.columnWidth(2), 100)
        self.assertEqual("Board", widget.configuration_table.item(0, 1).text())  # type: ignore[union-attr]
        self.assertEqual("Main", widget.configuration_table.item(0, 2).text())  # type: ignore[union-attr]
        self.assertEqual("启用", widget.configuration_table.item(0, 4).text())  # type: ignore[union-attr]
        self.assertEqual("BOM-V1", widget.configuration_table.item(0, 5).text())  # type: ignore[union-attr]
        self.assertEqual("复制为草稿并编辑", widget.copy_button.text())
        self.assertEqual("保存修改", widget.save_draft_button.text())
        self.assertFalse(widget.add_row_button.isEnabled())
        self.assertFalse(widget.remove_row_button.isEnabled())
        self.assertFalse(widget.save_draft_button.isEnabled())
        self.assertIn("不能直接修改", widget.edit_hint_label.text())
        self.assertFalse(widget.activate_button.isEnabled())
        self.assertTrue(widget.disable_button.isEnabled())
        widget.new_version_input.setText("V2")
        widget.copy_button.click()
        self.assertEqual(2, widget.configuration_table.rowCount())

        widget.configuration_table.selectRow(1)
        self.assertTrue(widget.add_row_button.isEnabled())
        self.assertTrue(widget.remove_row_button.isEnabled())
        self.assertTrue(widget.save_draft_button.isEnabled())
        self.assertIn("当前为草稿", widget.edit_hint_label.text())
        self.assertTrue(widget.activate_button.isEnabled())
        self.assertFalse(widget.disable_button.isEnabled())
        widget.assignment_table.item(0, 2).setText("M-2")  # type: ignore[union-attr]
        widget.save_draft_button.click()
        widget.activate_button.click()
        self.assertFalse(widget.activate_button.isEnabled())
        self.assertTrue(widget.disable_button.isEnabled())
        widget.disable_button.click()
        self.assertTrue(widget.activate_button.isEnabled())
        self.assertFalse(widget.disable_button.isEnabled())
        self.assertEqual(
            "M-2",
            repository.get("501000087", "V2").required_material("SMT-01", "F-01"),
        )
        self.assertEqual(
            [
                VoicePrompt.CONFIGURATION_ACTIVATED,
                VoicePrompt.CONFIGURATION_DISABLED,
            ],
            announcer.prompts,
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
        run_widget = ProductionRunManagementWidget(runs, clock=self.clock)
        self.addCleanup(run_widget.close)
        run_widget.resize(1180, 700)
        run_widget.show()
        self.app.processEvents()
        run_widget.status_combo.setCurrentIndex(3)
        run_widget.query_input.setText("RUN-UI")
        run_widget.refresh()

        run_id_item = run_widget.run_table.item(0, 0)
        assert run_id_item is not None
        self.assertEqual("RUN-UI", run_id_item.toolTip())
        self.assertEqual(6, run_widget.run_table.columnCount())
        product_version_header = run_widget.run_table.horizontalHeaderItem(1)
        assert product_version_header is not None
        self.assertEqual("产品 / 版本", product_version_header.text())
        self.assertGreaterEqual(run_widget.run_table.columnWidth(0), 160)
        self.assertEqual(0, run_widget.run_table.horizontalScrollBar().maximum())
        self.assertEqual(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
            run_widget.run_table.horizontalScrollBarPolicy(),
        )
        self.assertIn("更新于 12:00", run_widget.status_label.text())

        resumed: list[str] = []
        run_widget.resume_requested.connect(resumed.append)
        run_widget.resume_button.click()
        self.assertEqual(["RUN-UI"], resumed)
        self.assertEqual(1, run_widget.station_table.rowCount())
        self.assertEqual(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
            run_widget.station_table.horizontalScrollBarPolicy(),
        )
        self.assertEqual(0, run_widget.station_table.horizontalScrollBar().maximum())
        self.assertIn("OP-UI", run_widget.snapshot_label.text())
        self.assertEqual("RUN-UI", run_widget.run_summary_title.text())
        self.assertEqual("已中断", run_widget.run_status_chip.text())
        self.assertEqual("0 / 1", run_widget.run_progress_chip.text())
        self.assertEqual("NG 0", run_widget.run_ng_chip.text())
        self.assertIn("结束/中断：2026-07-14 10:01", run_widget.snapshot_label.text())
        self.assertIn("中断原因：换线", run_widget.snapshot_label.text())
        self.assertIsInstance(run_widget.started_from_input, QDateTimeEdit)
        self.assertEqual("yyyy-MM-dd HH:mm", run_widget.started_from_input.displayFormat())
        run_widget.date_range.today_button.click()
        self.assertEqual(0, run_widget.run_table.rowCount())
        run_widget.date_range.seven_days_button.click()
        self.assertEqual(1, run_widget.run_table.rowCount())

        audit_widget = AuditLogWidget(
            SqliteAuditRepository(self.connection), clock=self.clock
        )
        self.addCleanup(audit_widget.close)
        audit_widget.actor_input.setText("OP-UI")
        audit_widget.entity_type_input.setText("PRODUCTION_RUN")
        audit_widget.refresh()
        self.assertEqual(2, audit_widget.audit_table.rowCount())
        first_action = audit_widget.audit_table.item(0, 4)
        assert first_action is not None
        self.assertEqual("中断", first_action.text())
        self.assertEqual("INTERRUPT", first_action.toolTip())
        entity_key = audit_widget.audit_table.item(0, 3)
        assert entity_key is not None
        self.assertEqual(entity_key.text(), entity_key.toolTip())
        self.assertTrue(audit_widget.audit_table.isColumnHidden(6))
        self.assertTrue(audit_widget.audit_table.isColumnHidden(7))
        self.assertIn("生产运行", audit_widget.detail_title.text())
        self.assertIn("RUN-UI", audit_widget.detail_meta.text())
        self.assertEqual(RunStatus.INTERRUPTED, runs.get("RUN-UI").status)
        self.assertIsInstance(audit_widget.started_from_input, QDateTimeEdit)
        self.assertNotIn("ISO", audit_widget.status_label.text())
        self.assertIn("更新于 12:00", audit_widget.status_label.text())

    def test_audit_page_distinguishes_unqueried_zero_and_refreshes_when_activated(self) -> None:
        repository = SqliteAuditRepository(self.connection)
        widget = AuditLogWidget(
            repository,
            clock=lambda: datetime.now(UTC),
        )
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
        widget = ProductionRunManagementWidget(runs, clock=self.clock)
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
        announcer = FakeAnnouncementSink()
        widget = ScanWidget(
            configurations,
            runs,
            SilentAudio(),
            clock=lambda: datetime(2026, 7, 14, 11, 0, tzinfo=UTC),
            run_id_factory=lambda: "RUN-RESUME",
            runs=runs,
            operator_provider=self.session.require,
            announcer=announcer,
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
        self.assertEqual(
            [
                VoicePrompt.SCAN_DEVICE,
                VoicePrompt.RUN_INTERRUPTED,
                VoicePrompt.SCAN_DEVICE,
                VoicePrompt.RUN_INTERRUPTED,
            ],
            announcer.prompts,
        )

    def test_management_pages_report_invalid_or_missing_actions(self) -> None:
        announcer = FakeAnnouncementSink()
        bom_widget = BomManagementWidget(
            SqliteBomRepository(self.connection),
            self.session.require,
            announcer=announcer,
        )
        self.addCleanup(bom_widget.close)
        self.assertFalse(hasattr(bom_widget, "activate_button"))
        self.assertFalse(hasattr(bom_widget, "disable_button"))
        bom_import_requests: list[bool] = []
        bom_widget.import_requested.connect(lambda: bom_import_requests.append(True))
        self.assertFalse(bom_widget.import_button.isHidden())
        bom_widget.import_button.click()
        self.assertEqual([True], bom_import_requests)
        bom_widget.compare_button.click()
        self.assertIn("请选择", bom_widget.status_label.text())

        config_widget = ConfigurationManagementWidget(
            SqliteProductConfigurationRepository(self.connection),
            self.session.require,
            announcer=announcer,
        )
        self.addCleanup(config_widget.close)
        self.assertFalse(config_widget.activate_button.isEnabled())
        self.assertFalse(config_widget.disable_button.isEnabled())
        configuration_import_requests: list[bool] = []
        config_widget.import_requested.connect(
            lambda: configuration_import_requests.append(True)
        )
        self.assertFalse(config_widget.import_button.isHidden())
        config_widget.import_button.click()
        self.assertEqual([True], configuration_import_requests)
        config_widget.copy_button.click()
        config_widget.activate_button.click()
        config_widget.validate_button.click()
        config_widget.save_draft_button.click()
        self.assertIn("产品配置", config_widget.status_label.text())
        self.assertEqual(
            [VoicePrompt.LIFECYCLE_FAILED],
            announcer.prompts,
        )

        run_widget = ProductionRunManagementWidget(
            SqliteProductionRunRepository(self.connection), clock=self.clock
        )
        self.addCleanup(run_widget.close)
        self.assertIsInstance(run_widget.started_to_input, QDateTimeEdit)
        self.assertEqual("yyyy-MM-dd HH:mm", run_widget.started_to_input.displayFormat())


if __name__ == "__main__":
    unittest.main()
