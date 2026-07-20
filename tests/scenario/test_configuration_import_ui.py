import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from openpyxl import load_workbook
from PySide6.QtWidgets import QApplication

from smt_guard.configuration import ImportValidationError
from smt_guard.feedback import VoicePrompt
from smt_guard.importing import ImportResult
from smt_guard.scan import ProductConfiguration
from smt_guard.ui.importing import ConfigurationImportWidget


def sample_result() -> ImportResult:
    return ImportResult(
        None,
        ProductConfiguration("501000087", "V1", {("SMT-01", "F-01"): "013000081"}),
    )


class FakeImportWorkflow:
    def __init__(
        self,
        result: ImportResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[tuple[object, ...]] = []

    def import_configuration(
        self,
        station_path: Path,
        *,
        product_code: str,
        version: str,
        station_sheet: str,
    ) -> ImportResult:
        self.calls.append(("configuration", station_path, product_code, version, station_sheet))
        if self.error is not None:
            raise self.error
        if self.result is None:
            raise AssertionError("Fake result was not configured")
        return self.result


class FakeAnnouncementSink:
    def __init__(self) -> None:
        self.prompts: list[VoicePrompt] = []

    def announce(self, prompt: VoicePrompt) -> None:
        self.prompts.append(prompt)


class ConfigurationImportWidgetTests(unittest.TestCase):
    app: QApplication

    @classmethod
    def setUpClass(cls) -> None:
        application = QApplication.instance()
        cls.app = application if isinstance(application, QApplication) else QApplication([])

    def make_widget(
        self,
        workflow: FakeImportWorkflow,
        announcer: FakeAnnouncementSink | None = None,
    ) -> ConfigurationImportWidget:
        widget = ConfigurationImportWidget(workflow, announcer=announcer)
        self.addCleanup(widget.close)
        return widget

    @staticmethod
    def fill_required_inputs(widget: ConfigurationImportWidget) -> None:
        widget.product_code_input.setText(" 501000087 ")
        widget.version_input.setText(" V1 ")
        widget.station_path_input.setText(" C:/imports/stations.xlsx ")
        widget.station_sheet_input.setText(" Stations ")

    def test_executes_direct_import_and_previews_two_columns(self) -> None:
        workflow = FakeImportWorkflow(result=sample_result())
        announcer = FakeAnnouncementSink()
        widget = self.make_widget(workflow, announcer)
        self.fill_required_inputs(widget)

        widget.station_import_button.click()

        self.assertEqual(
            [
                (
                    "configuration",
                    Path("C:/imports/stations.xlsx"),
                    "501000087",
                    "V1",
                    "Stations",
                )
            ],
            workflow.calls,
        )
        self.assertEqual(2, widget.assignment_table.columnCount())
        self.assertEqual(1, widget.assignment_table.rowCount())
        self.assertEqual("F-01", widget.assignment_table.item(0, 0).text())  # type: ignore[union-attr]
        self.assertEqual("013000081", widget.assignment_table.item(0, 1).text())  # type: ignore[union-attr]
        self.assertEqual("success", widget.status_label.property("feedbackState"))
        self.assertEqual("导入并使用", widget.station_import_button.text())
        self.assertIn("已启用，可直接开始扫码", widget.status_label.text())
        self.assertEqual([VoicePrompt.CONFIGURATION_IMPORTED], announcer.prompts)

    @patch("smt_guard.ui.importing.QFileDialog.getSaveFileName")
    def test_downloads_a_two_column_template(self, get_save_file_name: object) -> None:
        widget = self.make_widget(FakeImportWorkflow(result=sample_result()))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "configuration.xlsx"
            get_save_file_name.return_value = (str(path), "Excel 工作簿 (*.xlsx)")  # type: ignore[attr-defined]

            widget.template_button.click()

            workbook = load_workbook(path, read_only=True)
            try:
                sheet = workbook["Worksheet"]
                self.assertEqual(("站位编码", "物料编码"), next(sheet.values))
            finally:
                workbook.close()

    def test_exposes_single_drag_drop_zone_with_selected_file_feedback(self) -> None:
        widget = self.make_widget(FakeImportWorkflow(result=sample_result()))
        self.assertTrue(widget.station_drop_zone.acceptDrops())
        widget.station_path_input.setText("C:/imports/stations.xlsx")
        self.assertEqual("stations.xlsx", widget.station_drop_zone.path_label.text())

    def test_displays_workflow_error_without_modal_dialog(self) -> None:
        workflow = FakeImportWorkflow(error=ImportValidationError("Row 7: unknown station"))
        announcer = FakeAnnouncementSink()
        widget = self.make_widget(workflow, announcer)
        self.fill_required_inputs(widget)
        widget.station_import_button.click()
        self.assertIn("第 7 行", widget.status_label.text())
        self.assertIn("未找到站位", widget.status_label.text())
        self.assertEqual("error", widget.status_label.property("feedbackState"))
        self.assertEqual([VoicePrompt.IMPORT_FAILED], announcer.prompts)

    def test_rejects_blank_required_input_before_calling_workflow(self) -> None:
        workflow = FakeImportWorkflow(result=sample_result())
        widget = self.make_widget(workflow)
        widget.station_path_input.setText("C:/imports/stations.xlsx")
        widget.station_import_button.click()
        self.assertEqual([], workflow.calls)
        self.assertIn("产品编码", widget.status_label.text())

    def test_translates_a_duplicate_configuration_error(self) -> None:
        workflow = FakeImportWorkflow(
            error=ValueError("Duplicate product configuration: 501000087/V1")
        )
        widget = self.make_widget(workflow)
        self.fill_required_inputs(widget)

        widget.station_import_button.click()

        self.assertIn("产品配置已存在", widget.status_label.text())
        self.assertIn("请填写新的配置版本", widget.status_label.text())

    def test_full_screen_workflow_stays_centered_at_a_readable_width(self) -> None:
        widget = self.make_widget(FakeImportWorkflow(result=sample_result()))
        widget.resize(1920, 900)
        widget.show()
        self.app.processEvents()
        self.assertLessEqual(widget.workflow_shell.width(), 1080)
        left_margin = widget.workflow_shell.geometry().left()
        right_margin = widget.width() - widget.workflow_shell.geometry().right() - 1
        self.assertLessEqual(abs(left_margin - right_margin), 24)
