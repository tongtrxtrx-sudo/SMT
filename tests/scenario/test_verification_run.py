import unittest
from datetime import UTC, datetime

from smt_guard.feedback import FeedbackTone
from smt_guard.records import InMemoryAttemptRepository
from smt_guard.run import VerificationRun
from smt_guard.scan import ProductConfiguration, ScanStep
from smt_guard.verification import VerificationResult


class FakeAudioSink:
    def __init__(self) -> None:
        self.tones: list[FeedbackTone] = []

    def emit(self, tone: FeedbackTone) -> None:
        self.tones.append(tone)


class FailingAttemptRepository(InMemoryAttemptRepository):
    def __init__(self) -> None:
        super().__init__()
        self.failed = False

    def append(self, attempt):  # type: ignore[no-untyped-def]
        if not self.failed:
            self.failed = True
            raise OSError("simulated database write failure")
        return super().append(attempt)


class VerificationRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.configuration = ProductConfiguration(
            "501000087",
            "V1",
            {
                ("SMT-01", "F-01"): "013000081",
                ("SMT-01", "F-02"): "005000103",
            },
        )
        self.repository = InMemoryAttemptRepository()
        self.audio = FakeAudioSink()
        self.timestamp = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)
        self.verification_run = VerificationRun(
            "RUN-1",
            self.configuration,
            self.repository,
            self.audio,
            clock=lambda: self.timestamp,
        )

    def scan_to_material(self, station: str = "F-01") -> None:
        self.verification_run.handle_scan("SMT-01")
        self.verification_run.handle_scan(station)

    def test_records_complete_ok_attempt(self) -> None:
        self.scan_to_material()

        update = self.verification_run.handle_scan("013000081")

        self.assertIsNotNone(update.attempt)
        assert update.attempt is not None
        self.assertEqual("RUN-1", update.attempt.run_id)
        self.assertEqual(self.timestamp, update.attempt.timestamp)
        self.assertEqual(VerificationResult.OK, update.attempt.result)
        self.assertFalse(update.attempt.repeated)
        self.assertEqual(1, update.feedback.completed_stations)
        self.assertEqual([FeedbackTone.OK], self.audio.tones)

    def test_preserves_ng_retry_and_counts_only_first_ok(self) -> None:
        self.scan_to_material()

        ng = self.verification_run.handle_scan("999999999")
        ok = self.verification_run.handle_scan("013000081")

        records = self.repository.list_for_run("RUN-1")
        self.assertEqual(
            [VerificationResult.NG, VerificationResult.OK],
            [record.result for record in records],
        )
        self.assertEqual(0, ng.feedback.completed_stations)
        self.assertEqual(1, ok.feedback.completed_stations)
        self.assertFalse(records[0].repeated)
        self.assertFalse(records[1].repeated)

    def test_marks_post_completion_check_as_repeated_without_double_progress(self) -> None:
        self.scan_to_material()
        self.verification_run.handle_scan("013000081")
        self.verification_run.handle_scan("F-01")

        repeated = self.verification_run.handle_scan("013000081")

        records = self.repository.list_for_run("RUN-1")
        self.assertTrue(records[-1].repeated)
        self.assertEqual(1, repeated.feedback.completed_stations)

    def test_rejected_order_does_not_create_attempt(self) -> None:
        update = self.verification_run.handle_scan("F-01")

        self.assertFalse(update.outcome.accepted)
        self.assertEqual(ScanStep.DEVICE, update.outcome.next_step)
        self.assertIsNone(update.attempt)
        self.assertEqual([], self.repository.list_for_run("RUN-1"))

    def test_failed_attempt_write_does_not_advance_scan_or_completion_state(self) -> None:
        verification_run = VerificationRun(
            "RUN-FAILED-WRITE",
            self.configuration,
            FailingAttemptRepository(),
            self.audio,
            clock=lambda: self.timestamp,
        )
        verification_run.handle_scan("SMT-01")
        verification_run.handle_scan("F-01")

        with self.assertRaises(OSError):
            verification_run.handle_scan("013000081")

        retried = verification_run.handle_scan("013000081")
        self.assertTrue(retried.outcome.accepted)
        self.assertEqual(VerificationResult.OK, retried.outcome.verification)


if __name__ == "__main__":
    unittest.main()
