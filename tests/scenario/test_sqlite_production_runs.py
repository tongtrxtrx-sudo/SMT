import sqlite3
import unittest
from datetime import UTC, datetime

from smt_guard.records import Attempt
from smt_guard.run import RunStatus, VerificationRun
from smt_guard.scan import ProductConfiguration
from smt_guard.sqlite import (
    SqliteDatabase,
    SqliteMasterDataRepository,
    SqliteProductConfigurationRepository,
    SqliteProductionRunRepository,
)
from smt_guard.verification import VerificationResult


class _SilentAudio:
    def emit(self, tone: object) -> None:
        del tone


class SqliteProductionRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.addCleanup(self.connection.close)
        SqliteDatabase(self.connection).initialize()
        self.configuration = ProductConfiguration(
            "501000087", "V1", {("SMT-01", "F-01"): "013000081"}
        )
        master_data = SqliteMasterDataRepository(self.connection)
        master_data.add_device("SMT-01", "Machine 1", "Line A")
        master_data.add_station("SMT-01", "F-01")
        SqliteProductConfigurationRepository(self.connection).save(self.configuration)
        self.repository = SqliteProductionRunRepository(self.connection)
        self.started_at = datetime(2026, 7, 14, 8, 0, tzinfo=UTC)

    def test_persists_and_interrupts_zero_scan_run_for_recovery(self) -> None:
        self.repository.start(
            "RUN-ZERO", self.configuration, operator="OP-01", started_at=self.started_at
        )

        self.repository.interrupt(
            "RUN-ZERO",
            operator="OP-01",
            interrupted_at=datetime(2026, 7, 14, 8, 5, tzinfo=UTC),
            reason="换线",
        )

        restored = SqliteProductionRunRepository(self.connection).get("RUN-ZERO")
        self.assertEqual("260714-001", restored.job_number)
        self.assertEqual(RunStatus.INTERRUPTED, restored.status)
        self.assertEqual("OP-01", restored.operator)
        self.assertEqual(0, restored.completed_stations)
        self.assertEqual(1, restored.total_stations)
        self.assertEqual("013000081", restored.configuration.required_material("SMT-01", "F-01"))

        running = self.repository.resume(
            "RUN-ZERO",
            operator="OP-01",
            resumed_at=datetime(2026, 7, 14, 8, 6, tzinfo=UTC),
        )
        service = VerificationRun.resume(
            running,
            self.repository,
            _SilentAudio(),
            clock=lambda: datetime(2026, 7, 14, 8, 6, tzinfo=UTC),
            runs=self.repository,
            completed_stations=self.repository.completed_station_keys("RUN-ZERO"),
        )
        self.assertEqual("RUN-ZERO", service.run_id)
        self.assertEqual(0, service.initial_feedback.completed_stations)

    def test_attempt_and_station_progress_rollback_together_on_write_failure(self) -> None:
        self.repository.start(
            "RUN-ATOMIC", self.configuration, operator="OP-01", started_at=self.started_at
        )
        self.connection.execute(
            "CREATE TRIGGER fail_attempt_insert BEFORE INSERT ON attempts "
            "BEGIN SELECT RAISE(ABORT, 'simulated failure'); END"
        )
        attempt = Attempt(
            None,
            datetime(2026, 7, 14, 8, 1, tzinfo=UTC),
            "RUN-ATOMIC",
            "501000087",
            "V1",
            "SMT-01",
            "F-01",
            "013000081",
            "013000081",
            VerificationResult.OK,
            False,
        )

        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.record_attempt(attempt)

        self.assertEqual([], self.repository.list_for_run("RUN-ATOMIC"))
        restored = self.repository.get("RUN-ATOMIC")
        self.assertEqual(RunStatus.RUNNING, restored.status)
        self.assertEqual(0, restored.completed_stations)

    def test_ok_attempt_completes_persisted_run_and_station(self) -> None:
        self.repository.start(
            "RUN-COMPLETE", self.configuration, operator="OP-01", started_at=self.started_at
        )
        stored = self.repository.record_attempt(
            Attempt(
                None,
                datetime(2026, 7, 14, 8, 1, tzinfo=UTC),
                "RUN-COMPLETE",
                "501000087",
                "V1",
                "SMT-01",
                "F-01",
                "013000081",
                "013000081",
                VerificationResult.OK,
                False,
            )
        )

        completed = self.repository.get("RUN-COMPLETE")
        self.assertIsNotNone(stored.id)
        self.assertEqual(RunStatus.COMPLETED, completed.status)
        self.assertEqual(1, completed.completed_stations)
        self.assertEqual(
            ["RUN-COMPLETE"],
            [item.run_id for item in self.repository.list_runs(RunStatus.COMPLETED)],
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute("UPDATE attempts SET scanned_material = 'x'")

    def test_searches_runs_and_exposes_snapshot_station_states(self) -> None:
        self.repository.start(
            "RUN-SEARCH", self.configuration, operator="OP-SEARCH", started_at=self.started_at
        )

        runs = self.repository.search_runs("501000087", operator="SEARCH", status=RunStatus.RUNNING)
        states = self.repository.list_station_states("RUN-SEARCH")

        self.assertEqual(["RUN-SEARCH"], [item.run_id for item in runs])
        self.assertEqual([("SMT-01", "F-01", False)], [
            (item.device_code, item.station_code, item.completed) for item in states
        ])

    def test_allocates_stable_short_job_numbers_and_searches_by_them(self) -> None:
        first = self.repository.start(
            "RUN-LONG-INTERNAL-1",
            self.configuration,
            operator="OP-01",
            started_at=self.started_at,
        )
        second = self.repository.start(
            "RUN-LONG-INTERNAL-2",
            self.configuration,
            operator="OP-01",
            started_at=self.started_at,
        )

        self.assertEqual("260714-001", first.job_number)
        self.assertEqual("260714-002", second.job_number)
        self.assertEqual(
            ["RUN-LONG-INTERNAL-2"],
            [run.run_id for run in self.repository.search_runs("260714-002")],
        )


if __name__ == "__main__":
    unittest.main()
