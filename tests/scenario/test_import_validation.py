import unittest

from smt_guard.configuration import ImportValidationError, ProductConfigurationBuilder
from smt_guard.master_data import MasterDataService


class ImportValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.master = MasterDataService()
        self.master.add_device("SMT-01", "Placement machine 1", "Line A")
        self.master.add_station("SMT-01", "F-01")
        self.builder = ProductConfigurationBuilder(self.master)
        self.materials = {"10002345": object(), "013000081": object()}

    def test_accepts_valid_station_assignment(self) -> None:
        configuration = self.builder.build(
            product_code="501000087",
            version="V1",
            materials=self.materials,
            station_rows=[
                {"设备编码": "SMT-01", "站位编码": "F-01", "物料编码": "10002345"}
            ],
        )

        self.assertEqual("10002345", configuration.required_material("SMT-01", "F-01"))

    def test_accepts_station_and_material_without_device_or_bom_membership(self) -> None:
        configuration = self.builder.build(
            "501000087",
            "V1",
            {},
            [{"站位编码": "F-01", "物料编码": "ANY-MATERIAL"}],
        )

        self.assertEqual(
            "ANY-MATERIAL", configuration.required_material("SMT-01", "F-01")
        )

    def test_rejects_missing_required_column(self) -> None:
        with self.assertRaises(ImportValidationError) as caught:
            self.builder.build(
                "501000087",
                "V1",
                self.materials,
                [{"设备编码": "SMT-01", "站位编码": "F-01"}],
            )

        self.assertIn("物料编码", str(caught.exception))

    def test_rejects_unknown_station_with_source_row(self) -> None:
        with self.assertRaises(ImportValidationError) as caught:
            self.builder.build(
                "501000087",
                "V1",
                self.materials,
                [
                    {
                        "设备编码": "SMT-01",
                        "站位编码": "F-99",
                        "物料编码": "99999999",
                        "_row_number": 7,
                    }
                ],
            )

        self.assertIn("7", str(caught.exception))
        self.assertIn("F-99", str(caught.exception))

    def test_rejects_mismatched_legacy_device_column(self) -> None:
        with self.assertRaises(ImportValidationError) as caught:
            self.builder.build(
                "501000087",
                "V1",
                self.materials,
                [{"设备编码": "SMT-99", "站位编码": "F-01", "物料编码": "10002345"}],
            )

        self.assertIn("belongs to device SMT-01", str(caught.exception))

    def test_rejects_unknown_station_under_device(self) -> None:
        with self.assertRaises(ImportValidationError):
            self.builder.build(
                "501000087",
                "V1",
                self.materials,
                [{"设备编码": "SMT-01", "站位编码": "F-99", "物料编码": "10002345"}],
            )

    def test_rejects_duplicate_device_and_station_assignment(self) -> None:
        row = {"设备编码": "SMT-01", "站位编码": "F-01", "物料编码": "10002345"}

        with self.assertRaises(ImportValidationError):
            self.builder.build("501000087", "V1", self.materials, [row, row.copy()])

    def test_rejects_empty_codes(self) -> None:
        with self.assertRaises(ImportValidationError):
            self.builder.build(
                "501000087",
                "V1",
                self.materials,
                [{"设备编码": "SMT-01", "站位编码": " ", "物料编码": "10002345"}],
            )

    def test_rejects_empty_station_table(self) -> None:
        with self.assertRaises(ImportValidationError):
            self.builder.build("501000087", "V1", self.materials, [])

    def test_building_configuration_does_not_mark_station_referenced(self) -> None:
        self.builder.build(
            "501000087",
            "V1",
            self.materials,
            [{"设备编码": "SMT-01", "站位编码": "F-01", "物料编码": "10002345"}],
        )

        self.assertFalse(self.master.get_station("SMT-01", "F-01").referenced)


if __name__ == "__main__":
    unittest.main()
