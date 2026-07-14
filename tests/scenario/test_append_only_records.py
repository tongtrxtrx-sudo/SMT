import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

from smt_guard.records import Attempt, InMemoryAttemptRepository
from smt_guard.verification import VerificationResult


def make_attempt(
    *,
    run_id: str = "RUN-1",
    scanned: str = "10002345",
    result: VerificationResult = VerificationResult.OK,
) -> Attempt:
    return Attempt(
        id=None,
        timestamp=datetime(2026, 7, 11, 10, 0, tzinfo=UTC),
        run_id=run_id,
        product_code="501000087",
        product_version="V1",
        device_code="SMT-01",
        station_code="F-01",
        expected_material="10002345",
        scanned_material=scanned,
        result=result,
        repeated=False,
    )


class AppendOnlyRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = InMemoryAttemptRepository()

    def test_appends_complete_ok_attempt(self) -> None:
        stored = self.repository.append(make_attempt())

        self.assertIsNotNone(stored.id)
        self.assertEqual(VerificationResult.OK, stored.result)
        self.assertEqual("SMT-01", stored.device_code)
        self.assertEqual("F-01", stored.station_code)

    def test_ng_and_retry_are_both_preserved(self) -> None:
        self.repository.append(
            make_attempt(scanned="10002346", result=VerificationResult.NG)
        )
        self.repository.append(make_attempt())

        records = self.repository.list_for_run("RUN-1")

        self.assertEqual(2, len(records))
        self.assertEqual(VerificationResult.NG, records[0].result)
        self.assertEqual(VerificationResult.OK, records[1].result)

    def test_attempt_is_immutable(self) -> None:
        attempt = make_attempt()

        with self.assertRaises(FrozenInstanceError):
            attempt.result = VerificationResult.NG  # type: ignore[misc]

    def test_repository_does_not_expose_update_or_delete(self) -> None:
        self.assertFalse(hasattr(self.repository, "update"))
        self.assertFalse(hasattr(self.repository, "delete"))

    def test_records_have_deterministic_identifier_order(self) -> None:
        first = self.repository.append(make_attempt())
        second = self.repository.append(make_attempt())

        records = self.repository.list_for_run("RUN-1")

        self.assertEqual([first.id, second.id], [record.id for record in records])


if __name__ == "__main__":
    unittest.main()
