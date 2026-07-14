import sqlite3
import unittest

from smt_guard.master_data import DuplicateCodeError, ReferencedEntityError
from smt_guard.sqlite import SqliteDatabase, SqliteMasterDataRepository


class SqliteMasterDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.addCleanup(self.connection.close)
        SqliteDatabase(self.connection).initialize()
        self.repository = SqliteMasterDataRepository(self.connection)

    def test_persists_normalized_device_and_station_data(self) -> None:
        self.repository.add_device(" SMT-01 ", " Machine 1 ", " Line A ")
        self.repository.add_station("SMT-01", " F-01 ")

        reloaded = SqliteMasterDataRepository(self.connection)

        self.assertEqual("SMT-01", reloaded.get_device("SMT-01").code)
        self.assertEqual("Machine 1", reloaded.get_device("SMT-01").name)
        self.assertEqual(["F-01"], [station.code for station in reloaded.list_stations("SMT-01")])

    def test_rejects_duplicate_codes(self) -> None:
        self.repository.add_device("SMT-01", "Machine 1", "Line A")
        self.repository.add_station("SMT-01", "F-01")

        with self.assertRaises(DuplicateCodeError):
            self.repository.add_device("SMT-01", "Duplicate", "Line B")
        with self.assertRaises(DuplicateCodeError):
            self.repository.add_station("SMT-01", "F-01")

    def test_bulk_station_creation_is_atomic(self) -> None:
        self.repository.add_device("SMT-01", "Machine 1", "Line A")
        self.repository.add_station("SMT-01", "F-02")

        with self.assertRaises(DuplicateCodeError):
            self.repository.bulk_add_stations("SMT-01", "F-", 1, 3, width=2)

        self.assertEqual(["F-02"], [item.code for item in self.repository.list_stations("SMT-01")])

    def test_persists_lifecycle_state_and_protects_referenced_station(self) -> None:
        self.repository.add_device("SMT-01", "Machine 1", "Line A")
        self.repository.add_station("SMT-01", "F-01")
        self.repository.disable_device("SMT-01")
        self.repository.disable_station("SMT-01", "F-01")
        self.repository.mark_station_referenced("SMT-01", "F-01")

        reloaded = SqliteMasterDataRepository(self.connection)

        self.assertFalse(reloaded.is_device_enabled("SMT-01"))
        self.assertFalse(reloaded.is_station_enabled("SMT-01", "F-01"))
        with self.assertRaises(ReferencedEntityError):
            reloaded.delete_station("SMT-01", "F-01")


if __name__ == "__main__":
    unittest.main()
