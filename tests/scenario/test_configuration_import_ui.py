import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from smt_guard.bom import BomDocument, Material, Product
from smt_guard.configuration import ImportValidationError
from smt_guard.feedback import VoicePrompt
from smt_guard.importing import ImportResult
from smt_guard.scan import ProductConfiguration
from smt_guard.ui.importing import ConfigurationImportWidget


def sample_result() -> ImportResult:
    document = BomDocument(
        product=Product("501000087", "BOM-1", "Control board", "控制板", "大板"),
        materials={"013000081": Material("013000081", "端子线", "26AWG", "1", "电子物料/电子线")},
    )
    configuration = ProductConfiguration("501000087", "V1", {("SMT-01", "F-01"): "013000081"})
    return ImportResult(document, configuration)


class FakeImportWorkflow:
    def __init__(self, result: ImportResult | None = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[tuple[object, ...]] = []

    def import_bom(self, bom_path: Path, *, version: str | None = None) -> BomDocument:
        del version
        self.calls.append(("bom", bom_path))
        if self.result is None:
            raise AssertionError("Fake result was not configured")
        return self.result.document

    def import_station_table(
        self,
        station_path: Path,
        *,
        version: str,
        station_sheet: str,
    ) -> ImportResult:
        self.calls.append(("stations", station_path, version, station_sheet))
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
        if application is None:
            cls.app = QApplication([])
        elif isinstance(application, QApplication):
            cls.app = application
        else:
            raise RuntimeError("A non-GUI Qt application already exists")

    def make_widget(
        self,
        workflow: FakeImportWorkflow,
        announcer: FakeAnnouncementSink | None = None,
    ) -> ConfigurationImportWidget:
        widget = ConfigurationImportWidget(workflow, announcer=announcer)
        self.addCleanup(widget.close)
        return widget

    def fill_required_inputs(self, widget: ConfigurationImportWidget) -> None:
        widget.bom_path_input.setText(" C:/imports/bom.xlsx ")
        widget.station_path_input.setText(" C:/imports/stations.xlsx ")
        widget.station_sheet_input.setText(" Stations ")
        widget.version_input.setText(" V1 ")

    def test_executes_import_and_previews_result(self) -> None:
        workflow = FakeImportWorkflow(result=sample_result())
        announcer = FakeAnnouncementSink()
        widget = self.make_widget(workflow, announcer)
        self.fill_required_inputs(widget)

        widget.bom_import_button.click()
        self.assertTrue(widget.bom_step.isHidden())
        self.assertFalse(widget.station_step.isHidden())
        self.assertIn("501000087", widget.bom_summary_label.text())
        widget.review_button.click()
        self.assertFalse(widget.validation_step.isHidden())
        widget.station_import_button.click()

        self.assertEqual(
            [
                ("bom", Path("C:/imports/bom.xlsx")),
                ("stations", Path("C:/imports/stations.xlsx"), "V1", "Stations"),
            ],
            workflow.calls,
        )
        self.assertIn("501000087", widget.product_label.text())
        self.assertIn("1", widget.material_count_label.text())
        self.assertEqual(1, widget.assignment_table.rowCount())
        material_item = widget.assignment_table.item(0, 2)
        assert material_item is not None
        self.assertEqual("013000081", material_item.text())
        self.assertEqual("success", widget.status_label.property("feedbackState"))
        self.assertFalse(widget.station_import_button.isEnabled())
        self.assertIn("已启用", widget.validation_label.text())
        self.assertEqual(
            [VoicePrompt.BOM_IMPORTED, VoicePrompt.CONFIGURATION_IMPORTED],
            announcer.prompts,
        )

    def test_exposes_drag_drop_zones_with_selected_file_feedback(self) -> None:
        widget = self.make_widget(FakeImportWorkflow(result=sample_result()))

        self.assertTrue(widget.bom_drop_zone.acceptDrops())
        self.assertTrue(widget.station_drop_zone.acceptDrops())
        widget.bom_path_input.setText("C:/imports/bom.xlsx")
        widget.station_path_input.setText("C:/imports/stations.xlsx")

        self.assertEqual("bom.xlsx", widget.bom_drop_zone.path_label.text())
        self.assertEqual("stations.xlsx", widget.station_drop_zone.path_label.text())

    def test_displays_workflow_error_without_modal_dialog(self) -> None:
        workflow = FakeImportWorkflow(error=ImportValidationError("Row 7: unknown material"))
        announcer = FakeAnnouncementSink()
        widget = self.make_widget(workflow, announcer)
        self.fill_required_inputs(widget)

        widget.bom_import_button.click()
        widget.review_button.click()
        widget.station_import_button.click()

        self.assertIn("Row 7", widget.status_label.text())
        self.assertEqual("error", widget.status_label.property("feedbackState"))
        self.assertEqual([VoicePrompt.IMPORT_FAILED], announcer.prompts)

    def test_translates_wrong_import_order_into_operator_guidance(self) -> None:
        workflow = FakeImportWorkflow(
            error=ImportValidationError("Import a BOM before importing a station table")
        )
        widget = self.make_widget(workflow)
        self.fill_required_inputs(widget)

        widget.station_import_button.click()

        self.assertEqual("请先导入 BOM，再导入站位表。", widget.status_label.text())
        self.assertNotIn("Import", widget.status_label.text())

    def test_rejects_blank_required_input_before_calling_workflow(self) -> None:
        workflow = FakeImportWorkflow(result=sample_result())
        announcer = FakeAnnouncementSink()
        widget = self.make_widget(workflow, announcer)
        widget.bom_path_input.clear()

        widget.bom_import_button.click()

        self.assertEqual([], workflow.calls)
        self.assertIn("BOM", widget.status_label.text())
        self.assertEqual([VoicePrompt.IMPORT_FAILED], announcer.prompts)


if __name__ == "__main__":
    unittest.main()
