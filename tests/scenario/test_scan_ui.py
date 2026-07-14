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

        widget.start_button.click()

        self.assertEqual(1, widget.configuration_combo.count())
        self.assertIn("RUN-1", widget.run_label.text())
        self.assertTrue(widget.scan_input.isEnabled())
        self.assertIn("设备", widget.feedback_label.text())
        self.assertEqual([VoicePrompt.RUN_STARTED], self.announcements.prompts)

    def test_ok_scan_flow_updates_prompt_progress_and_history(self) -> None:
        widget = self.make_widget([self.configuration])
        widget.start_button.click()

        self.scan(widget, "SMT-01")
        self.assertIn("站位", widget.feedback_label.text())
        self.scan(widget, "F-01")
        self.assertIn("物料", widget.feedback_label.text())
        self.scan(widget, "013000081")

        self.assertEqual("ok", widget.feedback_label.property("feedbackState"))
        self.assertEqual(1, widget.progress_bar.value())
        self.assertEqual(1, widget.attempt_table.rowCount())
        self.assertEqual([FeedbackTone.OK], self.audio.tones)
        self.assertEqual(
            [VoicePrompt.RUN_STARTED, VoicePrompt.RUN_COMPLETED],
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
        widget.start_button.click()
        self.scan(widget, "SMT-01")
        self.scan(widget, "F-01")

        self.scan(widget, "999999999")

        self.assertEqual("ng", widget.feedback_label.property("feedbackState"))
        self.assertIn("013000081", widget.expected_label.text())
        self.assertIn("999999999", widget.scanned_label.text())
        self.assertEqual(0, widget.progress_bar.value())
        self.assertEqual(1, widget.attempt_table.rowCount())
        self.assertEqual(
            [VoicePrompt.RUN_STARTED, VoicePrompt.MATERIAL_NG],
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
                VoicePrompt.RUN_STARTED,
                VoicePrompt.SCAN_REJECTED,
                VoicePrompt.RUN_REPLACED,
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
            [VoicePrompt.RUN_STARTED, VoicePrompt.MATERIAL_OK],
            self.announcements.prompts,
        )


if __name__ == "__main__":
    unittest.main()
