import csv
import os
import sqlite3
import unittest
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from openpyxl import Workbook
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from smt_guard.app import ApplicationRuntime, create_runtime
from smt_guard.feedback import FeedbackTone, VoicePrompt
from smt_guard.scan import ProductConfiguration
from smt_guard.ui.operator import OperatorSessionWidget
from smt_guard.ui.records import RecordQueryWidget
from smt_guard.ui.runs import ProductionRunManagementWidget


class FakeAudioSink:
    def __init__(self) -> None:
        self.tones: list[FeedbackTone] = []

    def emit(self, tone: FeedbackTone) -> None:
        self.tones.append(tone)


class FakeAnnouncementSink:
    def __init__(self) -> None:
        self.prompts: list[VoicePrompt] = []

    def announce(self, prompt: VoicePrompt) -> None:
        self.prompts.append(prompt)


class ApplicationCompositionTests(unittest.TestCase):
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
        self.data_directory = Path(temporary.name)
        self.announcements = FakeAnnouncementSink()
        self.runtime = self.create_runtime()
        self.addCleanup(self.runtime.close)

    def create_runtime(self) -> ApplicationRuntime:
        return create_runtime(
            self.data_directory,
            audio=FakeAudioSink(),
            announcements=self.announcements,
            clock=lambda: datetime(2026, 7, 11, 12, 15, tzinfo=UTC),
            run_id_factory=lambda: "RUN-1",
        )

    def write_import_workbooks(self) -> tuple[Path, Path]:
        bom_path = self.data_directory / "bom.xlsx"
        bom = Workbook()
        bom_sheet = bom.active
        if bom_sheet is None:
            raise AssertionError("New workbook did not create a default worksheet")
        bom_sheet.title = "Worksheet"
        bom_sheet.append(
            [
                "BOM编号",
                "BOM名称",
                "深度",
                "单位用量",
                "商品编号",
                "商品名",
                "商品规格",
                "商品分类",
            ]
        )
        bom_sheet.append(["BOM-1", "Board", "0", "1", "501000087", "控制板", "大板", ""])
        bom_sheet.append(
            ["", "", "1", "1", "013000081", "端子线", "26AWG", "电子物料/电子线"]
        )
        bom.save(bom_path)
        bom.close()

        station_path = self.data_directory / "stations.xlsx"
        stations = Workbook()
        station_sheet = stations.active
        if station_sheet is None:
            raise AssertionError("New workbook did not create a default worksheet")
        station_sheet.title = "Stations"
        station_sheet.append(["设备编码", "站位编码", "物料编码"])
        station_sheet.append(["SMT-01", "F-01", "013000081"])
        stations.save(station_path)
        stations.close()
        return bom_path, station_path

    def scanner_enter(self, code: str) -> None:
        QTest.keyClicks(self.runtime.scan_widget.scan_input, code)
        QTest.keyClick(self.runtime.scan_widget.scan_input, Qt.Key.Key_Return)
        self.app.processEvents()

    def test_composes_grouped_side_navigation(self) -> None:
        labels = [button.text() for button in self.runtime.window.navigation_buttons]

        self.assertEqual(
            [
                "扫码作业",
                "生产运行",
                "记录查询",
                "设备与站位",
                "导入配置",
                "BOM 管理",
                "产品配置",
                "审计日志",
            ],
            labels,
        )
        self.assertTrue(self.runtime.window.navigation_buttons[0].isChecked())
        self.assertEqual(180, self.runtime.window.side_navigation.width())
        self.assertIn("数据库正常", self.runtime.window.diagnostic_label.text())
        self.assertEqual("SMT 扫码防错", self.runtime.window.windowTitle())

    def test_empty_scan_state_opens_guided_import_page(self) -> None:
        self.assertEqual(
            self.runtime.window.SCAN_TAB,
            self.runtime.window.tab_widget.currentIndex(),
        )

        self.runtime.scan_widget.import_configuration_button.click()

        self.assertEqual(
            self.runtime.window.IMPORT_TAB,
            self.runtime.window.tab_widget.currentIndex(),
        )

    def test_persists_data_across_runtime_reopen(self) -> None:
        self.runtime.master_data.add_device("SMT-01", "Machine 1", "Line A")
        self.runtime.close()

        reopened = self.create_runtime()
        self.addCleanup(reopened.close)

        self.assertEqual("Machine 1", reopened.master_data.get_device("SMT-01").name)
        self.assertTrue((self.data_directory / "smt_guard.sqlite3").is_file())

    def test_import_completion_refreshes_scan_configurations(self) -> None:
        self.runtime.master_data.add_device("SMT-01", "Machine 1", "Line A")
        self.runtime.master_data.add_station("SMT-01", "F-01")
        self.runtime.configurations.save(
            ProductConfiguration(
                "501000087", "V1", {("SMT-01", "F-01"): "013000081"}
            )
        )
        self.assertEqual(0, self.runtime.scan_widget.configuration_combo.count())

        self.runtime.import_widget.import_completed.emit()
        self.app.processEvents()

        self.assertEqual(1, self.runtime.scan_widget.configuration_combo.count())

    def test_close_is_idempotent_and_releases_database(self) -> None:
        connection = self.runtime.connection

        self.runtime.close()
        self.runtime.close()

        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

    def test_full_import_scanner_and_record_export_workflow(self) -> None:
        self.runtime.operator_session.sign_in("OP-01")
        self.runtime.master_data.add_device("SMT-01", "Machine 1", "Line A")
        self.runtime.master_data.add_station("SMT-01", "F-01")
        bom_path, station_path = self.write_import_workbooks()
        import_widget = self.runtime.import_widget
        import_widget.bom_path_input.setText(str(bom_path))
        import_widget.station_path_input.setText(str(station_path))
        import_widget.station_sheet_input.setText("Stations")
        import_widget.version_input.setText("V1")

        import_widget.bom_import_button.click()
        import_widget.review_button.click()
        import_widget.station_import_button.click()
        self.runtime.scan_widget.start_button.click()
        self.scanner_enter("SMT-01")
        self.scanner_enter("F-01")
        self.scanner_enter("999999999")
        self.scanner_enter("013000081")

        stored = self.runtime.connection.execute(
            "SELECT scanned_material, result FROM attempts ORDER BY id"
        ).fetchall()
        self.assertEqual([("999999999", "NG"), ("013000081", "OK")], stored)
        self.assertEqual(2, self.runtime.scan_widget.attempt_table.rowCount())
        self.assertEqual(1, self.runtime.scan_widget.progress_bar.value())

        run_widget = self.runtime.window.tab_widget.widget(self.runtime.window.RUNS_TAB)
        if not isinstance(run_widget, ProductionRunManagementWidget):
            raise AssertionError("Run tab contains an unexpected widget")
        run_widget.view_records_button.click()
        self.assertEqual(1, run_widget.detail_tabs.currentIndex())
        self.assertEqual(2, run_widget.attempt_table.rowCount())
        self.assertIn("NG 1", run_widget.attempt_summary_label.text())
        direct_export_path = self.data_directory / "run-1-direct.csv"
        with patch(
            "smt_guard.ui.runs.QFileDialog.getSaveFileName",
            return_value=(str(direct_export_path), "CSV 文件 (*.csv)"),
        ):
            run_widget.export_button.click()
        self.assertTrue(direct_export_path.is_file())

        records_widget = self.runtime.window.tab_widget.widget(self.runtime.window.RECORDS_TAB)
        if not isinstance(records_widget, RecordQueryWidget):
            raise AssertionError("Records tab contains an unexpected widget")
        records_widget.run_id_input.setText("RUN-1")
        records_widget.query_button.click()
        export_path = self.data_directory / "run-1.csv"
        records_widget.export_path_input.setText(str(export_path))
        records_widget.export_button.click()
        with export_path.open("r", encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))

        self.assertEqual(["NG", "OK"], [row["结果"] for row in rows])
        provenance = self.runtime.connection.execute(
            "SELECT imported_by FROM bom_versions"
        ).fetchone()
        configuration_actor = self.runtime.connection.execute(
            "SELECT created_by FROM product_configurations"
        ).fetchone()
        run_actor = self.runtime.connection.execute(
            "SELECT operator FROM production_runs"
        ).fetchone()
        self.assertEqual(("OP-01",), provenance)
        self.assertEqual(("OP-01",), configuration_actor)
        self.assertEqual(("OP-01",), run_actor)
        self.assertEqual(
            [
                VoicePrompt.BOM_IMPORTED,
                VoicePrompt.CONFIGURATION_IMPORTED,
                VoicePrompt.SCAN_DEVICE,
                VoicePrompt.SCAN_STATION,
                VoicePrompt.SCAN_MATERIAL,
                VoicePrompt.MATERIAL_NG,
                VoicePrompt.RUN_COMPLETED,
                VoicePrompt.RECORDS_EXPORTED,
                VoicePrompt.RECORDS_EXPORTED,
            ],
            self.announcements.prompts,
        )

    def test_operator_control_rejects_blank_and_updates_shared_session(self) -> None:
        control = self.runtime.window.findChild(OperatorSessionWidget)
        if control is None:
            self.fail("Missing operator session control")

        control.sign_in_button.click()
        self.assertIn("操作员", control.status_label.text())
        control.operator_input.setText(" OP-02 ")
        control.sign_in_button.click()

        self.assertEqual("OP-02", self.runtime.operator_session.require())
        self.assertTrue(control.operator_input.isHidden())
        self.assertFalse(control.current_label.isHidden())
        self.assertIn("OP-02", control.current_label.text())
        control.switch_button.click()
        self.assertFalse(control.operator_input.isHidden())
        self.assertEqual([VoicePrompt.OPERATOR_CONFIRMED], self.announcements.prompts)


if __name__ == "__main__":
    unittest.main()
