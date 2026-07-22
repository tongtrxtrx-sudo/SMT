import unittest

from smt_guard.master_data import (
    DuplicateCodeError,
    MasterDataService,
    ReferencedEntityError,
)


class DeviceStationMasterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = MasterDataService()

    def test_bulk_creates_requested_station_range(self) -> None:
        self.service.add_device("SMT-01", "Placement machine 1", "Line A")

        self.service.bulk_add_stations("SMT-01", "F-", 1, 60, width=2)

        self.assertEqual(60, len(self.service.list_stations("SMT-01")))
        self.assertEqual("F-01", self.service.list_stations("SMT-01")[0].code)
        self.assertEqual("F-60", self.service.list_stations("SMT-01")[-1].code)

    def test_rejects_duplicate_device_code(self) -> None:
        self.service.add_device("SMT-01", "Placement machine 1", "Line A")

        with self.assertRaises(DuplicateCodeError):
            self.service.add_device("SMT-01", "Duplicate", "Line B")

    def test_station_code_is_globally_unique(self) -> None:
        self.service.add_device("SMT-01", "Placement machine 1", "Line A")
        self.service.add_device("SMT-02", "Placement machine 2", "Line A")
        self.service.add_station("SMT-01", "F-01")

        with self.assertRaises(DuplicateCodeError):
            self.service.add_station("SMT-02", "F-01")

    def test_referenced_station_can_be_disabled_but_not_deleted(self) -> None:
        self.service.add_device("SMT-01", "Placement machine 1", "Line A")
        self.service.add_station("SMT-01", "F-01")
        self.service.mark_station_referenced("SMT-01", "F-01")

        self.service.disable_station("SMT-01", "F-01")

        self.assertFalse(self.service.get_station("SMT-01", "F-01").enabled)
        with self.assertRaises(ReferencedEntityError):
            self.service.delete_station("SMT-01", "F-01")


if __name__ == "__main__":
    unittest.main()
