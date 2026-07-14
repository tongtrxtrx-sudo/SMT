import sqlite3
import unittest
from datetime import UTC, datetime

from smt_guard.records import Attempt
from smt_guard.scan import ProductConfiguration
from smt_guard.sqlite import (
    DuplicateConfigurationError,
    SqliteAttemptRepository,
    SqliteDatabase,
    SqliteMasterDataRepository,
    SqliteProductConfigurationRepository,
)
from smt_guard.verification import VerificationResult


def make_attempt(
    *,
    run_id: str = "RUN-1",
    scanned: str = "013000081",
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
        expected_material="013000081",
        scanned_material=scanned,
        result=result,
        repeated=False,
    )


class SqliteConfigurationRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.addCleanup(self.connection.close)
        SqliteDatabase(self.connection).initialize()
        master_data = SqliteMasterDataRepository(self.connection)
        master_data.add_device("SMT-01", "Machine 1", "Line A")
        master_data.add_station("SMT-01", "F-01")

    def test_round_trips_configuration_and_preserves_leading_zeroes(self) -> None:
        repository = SqliteProductConfigurationRepository(self.connection)
        configuration = ProductConfiguration(
            "501000087", "V1", {("SMT-01", "F-01"): "013000081"}
        )

        repository.save(configuration)
        loaded = SqliteProductConfigurationRepository(self.connection).get("501000087", "V1")

        self.assertEqual(configuration, loaded)
        self.assertEqual("013000081", loaded.required_material("SMT-01", "F-01"))

    def test_rejects_duplicate_configuration_identity_and_keeps_versions_distinct(self) -> None:
        repository = SqliteProductConfigurationRepository(self.connection)
        version_one = ProductConfiguration(
            "501000087", "V1", {("SMT-01", "F-01"): "013000081"}
        )
        version_two = ProductConfiguration(
            "501000087", "V2", {("SMT-01", "F-01"): "005000103"}
        )
        repository.save(version_one)
        repository.save(version_two)

        with self.assertRaises(DuplicateConfigurationError):
            repository.save(version_one)

        self.assertEqual(version_two, repository.get("501000087", "V2"))

    def test_appends_and_round_trips_attempts_in_identifier_order(self) -> None:
        repository = SqliteAttemptRepository(self.connection)
        first = repository.append(
            make_attempt(scanned="999", result=VerificationResult.NG)
        )
        second = repository.append(make_attempt())

        records = SqliteAttemptRepository(self.connection).list_for_run("RUN-1")

        self.assertEqual([first.id, second.id], [record.id for record in records])
        self.assertEqual(
            [VerificationResult.NG, VerificationResult.OK],
            [record.result for record in records],
        )
        self.assertEqual(datetime(2026, 7, 11, 10, 0, tzinfo=UTC), records[0].timestamp)

    def test_attempt_repository_is_append_only(self) -> None:
        repository = SqliteAttemptRepository(self.connection)

        self.assertFalse(hasattr(repository, "update"))
        self.assertFalse(hasattr(repository, "delete"))

    def test_disabled_station_removes_old_configuration_from_scan_choices(self) -> None:
        master_data = SqliteMasterDataRepository(self.connection)
        repository = SqliteProductConfigurationRepository(self.connection)
        repository.save(
            ProductConfiguration(
                "501000087", "V1", {("SMT-01", "F-01"): "013000081"}
            )
        )

        master_data.disable_station("SMT-01", "F-01")

        self.assertEqual([], repository.list_configurations())


if __name__ == "__main__":
    unittest.main()
