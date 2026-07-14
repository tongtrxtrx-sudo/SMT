import unittest

from smt_guard.feedback import FeedbackController, FeedbackTone, VisualIntent
from smt_guard.scan import ScanStep
from smt_guard.verification import VerificationResult


class FakeAudioSink:
    def __init__(self) -> None:
        self.tones: list[FeedbackTone] = []

    def emit(self, tone: FeedbackTone) -> None:
        self.tones.append(tone)


class OperatorFeedbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.audio = FakeAudioSink()
        self.controller = FeedbackController(total_stations=2, audio=self.audio)

    def test_waiting_state_names_required_scan(self) -> None:
        state = self.controller.waiting(ScanStep.STATION)

        self.assertIn("站位", state.message)
        self.assertEqual(VisualIntent.NEUTRAL, state.intent)

    def test_ok_state_is_green_and_emits_ok_tone(self) -> None:
        state = self.controller.verified(
            expected="10002345",
            scanned="10002345",
            result=VerificationResult.OK,
            station_newly_completed=True,
        )

        self.assertEqual(VisualIntent.OK, state.intent)
        self.assertEqual("10002345", state.expected_material)
        self.assertEqual("10002345", state.scanned_material)
        self.assertEqual([FeedbackTone.OK], self.audio.tones)

    def test_ng_state_is_red_and_does_not_increment_progress(self) -> None:
        state = self.controller.verified(
            expected="10002345",
            scanned="10002346",
            result=VerificationResult.NG,
            station_newly_completed=False,
        )

        self.assertEqual(VisualIntent.NG, state.intent)
        self.assertEqual(0, state.completed_stations)
        self.assertEqual([FeedbackTone.NG], self.audio.tones)

    def test_progress_increments_only_for_newly_completed_station(self) -> None:
        first = self.controller.verified(
            "10002345", "10002345", VerificationResult.OK, station_newly_completed=True
        )
        repeat = self.controller.verified(
            "10002345", "10002345", VerificationResult.OK, station_newly_completed=False
        )

        self.assertEqual(1, first.completed_stations)
        self.assertEqual(1, repeat.completed_stations)

    def test_completion_is_shown_after_all_stations_are_ok(self) -> None:
        self.controller.verified(
            "10002345", "10002345", VerificationResult.OK, station_newly_completed=True
        )
        state = self.controller.verified(
            "10002346", "10002346", VerificationResult.OK, station_newly_completed=True
        )

        self.assertTrue(state.complete)
        self.assertIn("完成", state.message)


if __name__ == "__main__":
    unittest.main()
