import os
import unittest
from datetime import UTC, datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from smt_guard.feedback import FeedbackTone, VoicePrompt
from smt_guard.records import InMemoryAttemptRepository
from smt_guard.scan import ProductConfiguration
from smt_guard.ui.scanning import ScanWidget


class FakeConfigurationSource:
    def __init__(self, configurations: list[ProductConfiguration]) -> None:
        self._configurations = configurations

    def list_configurations(self) -> list[ProductConfiguration]:
        return self._configurations


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


class ScanWidgetTests(unittest.TestCase):
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
        self.configuration = ProductConfiguration(
            "501000087", "V1", {("SMT-01", "F-01"): "013000081"}
        )
        self.repository = InMemoryAttemptRepository()
        self.audio = FakeAudioSink()
        self.announcements = FakeAnnouncementSink()

    def make_widget(self, configurations: list[ProductConfiguration]) -> ScanWidget:
        widget = ScanWidget(
            FakeConfigurationSource(configurations),
            self.repository,
            self.audio,
            clock=lambda: datetime(2026, 7, 11, 12, 0, tzinfo=UTC),
            run_id_factory=lambda: "RUN-1",
            announcer=self.announcements,
        )
        self.addCleanup(widget.close)
        return widget

    @staticmethod
    def scan(widget: ScanWidget, code: str) -> None:
        widget.scan_input.setText(code)
        widget.submit_button.click()

    def test_loads_configuration_and_starts_run(self) -> None:
        widget = self.make_widget([self.configuration])

        self.assertIn("501000087 / V1", widget.product_summary_label.text())
        self.assertFalse(widget.selection_card.isHidden())

        widget.start_button.click()

        self.assertEqual(1, widget.configuration_combo.count())
        self.assertIn("RUN-1", widget.run_label.text())
        self.assertTrue(widget.scan_input.isEnabled())
        self.assertIn("设备", widget.feedback_label.text())
        self.assertIn("#eff8ff", widget.feedback_label.styleSheet())
        self.assertFalse(widget.attempt_table.isVisible())
        self.assertTrue(widget.selection_card.isHidden())
        self.assertEqual("0 / 1", widget.progress_count_label.text())
        self.assertEqual([VoicePrompt.SCAN_DEVICE], self.announcements.prompts)

    def test_empty_configuration_guides_operator_to_import(self) -> None:
        widget = self.make_widget([])
        requested: list[bool] = []
        widget.import_requested.connect(lambda: requested.append(True))

        self.assertFalse(widget.start_button.isEnabled())
        self.assertFalse(widget.configuration_combo.isEnabled())
        self.assertFalse(widget.import_configuration_button.isHidden())
        widget.import_configuration_button.click()

        self.assertEqual([True], requested)

    def test_focus_status_and_history_keep_scanner_as_primary_input(self) -> None:
        widget = self.make_widget([self.configuration])
        widget.show()
        widget.start_button.click()
        self.app.processEvents()

        self.assertTrue(widget.scan_input.hasFocus())
        self.assertIn("已就绪", widget.scanner_status_button.text())
        widget.history_button.click()
        self.assertTrue(widget.attempt_table.isVisible())
        widget.history_button.click()
        self.assertFalse(widget.attempt_table.isVisible())

        widget.history_button.setFocus()
        self.app.processEvents()
        self.assertIn("未激活", widget.scanner_status_button.text())
        widget.scanner_status_button.click()
        self.app.processEvents()
        self.assertTrue(widget.scan_input.hasFocus())
        self.assertIn("已就绪", widget.scanner_status_button.text())

    def test_ok_scan_flow_updates_prompt_progress_and_history(self) -> None:
        widget = self.make_widget([self.configuration])
        widget.start_button.click()

        self.scan(widget, "SMT-01")
        self.assertIn("站位", widget.feedback_label.text())
        self.assertIn("#fffaeb", widget.feedback_label.styleSheet())
        self.scan(widget, "F-01")
        self.assertIn("物料", widget.feedback_label.text())
        self.assertFalse(widget.expected_label.isHidden())
        self.assertIn("#ecfdf3", widget.feedback_label.styleSheet())
        self.scan(widget, "013000081")

        self.assertEqual("ok", widget.feedback_label.property("feedbackState"))
        self.assertEqual(1, widget.progress_bar.value())
        self.assertEqual("1 / 1", widget.progress_count_label.text())
        self.assertFalse(widget.selection_card.isHidden())
        self.assertEqual(1, widget.attempt_table.rowCount())
        self.assertEqual([FeedbackTone.OK], self.audio.tones)
        self.assertEqual(
            [
                VoicePrompt.SCAN_DEVICE,
                VoicePrompt.SCAN_STATION,
                VoicePrompt.SCAN_MATERIAL,
                VoicePrompt.RUN_COMPLETED,
            ],
            self.announcements.prompts,
        )

    def test_completed_run_immediately_locks_scanning_and_keeps_terminal_state(self) -> None:
        widget = self.make_widget([self.configuration])
        widget.start_button.click()

        self.scan(widget, "SMT-01")
        self.scan(widget, "F-01")
        self.scan(widget, "013000081")

        self.assertFalse(widget.scan_input.isEnabled())
        self.assertFalse(widget.submit_button.isEnabled())
        self.assertEqual("", widget.scan_input.text())
        self.assertEqual("全部对料完成", widget.feedback_label.text())

        widget.scan_input.setText("STALE-SCAN")
        widget.scan_input.returnPressed.emit()

        self.assertEqual("", widget.scan_input.text())
        self.assertEqual("全部对料完成", widget.feedback_label.text())
        self.assertEqual(1, widget.attempt_table.rowCount())

    def test_ng_scan_shows_expected_and_scanned_material(self) -> None:
        widget = self.make_widget([self.configuration])
        widget.show()
        widget.start_button.click()
        self.scan(widget, "SMT-01")
        self.scan(widget, "F-01")

        self.scan(widget, "999999999")
        self.app.processEvents()

        self.assertEqual("ng", widget.feedback_label.property("feedbackState"))
        self.assertIn("#fef3f2", widget.feedback_label.styleSheet())
        self.assertIn("013000081", widget.expected_label.text())
        self.assertIn("999999999", widget.scanned_label.text())
        self.assertEqual(0, widget.progress_bar.value())
        self.assertEqual(1, widget.attempt_table.rowCount())
        self.assertTrue(widget.scan_input.hasFocus())
        self.assertIn("已就绪", widget.scanner_status_button.text())
        self.assertEqual(
            [
                VoicePrompt.SCAN_DEVICE,
                VoicePrompt.SCAN_STATION,
                VoicePrompt.SCAN_MATERIAL,
                VoicePrompt.MATERIAL_NG,
            ],
            self.announcements.prompts,
        )

    def test_explains_empty_configuration_state(self) -> None:
        widget = self.make_widget([])

        widget.start_button.click()

        self.assertFalse(widget.scan_input.isEnabled())
        self.assertIn("导入", widget.feedback_label.text())

    def test_invalid_scan_and_run_replacement_prioritize_latest_prompt(self) -> None:
        widget = self.make_widget([self.configuration])
        widget.start_button.click()
        self.scan(widget, "WRONG-DEVICE")
        widget.start_button.click()

        self.assertEqual(
            [
                VoicePrompt.SCAN_DEVICE,
                VoicePrompt.SCAN_REJECTED,
                VoicePrompt.SCAN_DEVICE,
            ],
            self.announcements.prompts,
        )

    def test_non_terminal_ok_scan_uses_material_ok_prompt(self) -> None:
        configuration = ProductConfiguration(
            "501000087",
            "V2",
            {
                ("SMT-01", "F-01"): "013000081",
                ("SMT-01", "F-02"): "005000103",
            },
        )
        widget = self.make_widget([configuration])
        widget.start_button.click()
        self.scan(widget, "SMT-01")
        self.scan(widget, "F-01")
        self.scan(widget, "013000081")

        self.assertEqual(
            [
                VoicePrompt.SCAN_DEVICE,
                VoicePrompt.SCAN_STATION,
                VoicePrompt.SCAN_MATERIAL,
                VoicePrompt.SCAN_STATION,
            ],
            self.announcements.prompts,
        )

    def test_attempt_time_is_displayed_to_minute_precision_only(self) -> None:
        widget = ScanWidget(
            FakeConfigurationSource([self.configuration]),
            self.repository,
            self.audio,
            clock=lambda: datetime(2026, 7, 11, 12, 34, 56, 789000, tzinfo=UTC),
            run_id_factory=lambda: "RUN-1",
            announcer=self.announcements,
        )
        self.addCleanup(widget.close)
        widget.start_button.click()
        self.scan(widget, "SMT-01")
        self.scan(widget, "F-01")
        self.scan(widget, "013000081")

        time_item = widget.attempt_table.item(0, 0)
        self.assertIsNotNone(time_item)
        if time_item is None:
            self.fail("Missing attempt timestamp cell")
        self.assertEqual("2026-07-11 12:34", time_item.text())
        self.assertEqual(56, self.repository.list_for_run("RUN-1")[0].timestamp.second)


if __name__ == "__main__":
    unittest.main()
