import unittest

from smt_guard.scan import ProductConfiguration, ScanSession, ScanStep


class OrderedScanTests(unittest.TestCase):
    def setUp(self) -> None:
        configuration = ProductConfiguration(
            product_code="501000087",
            version="V1",
            assignments={
                ("SMT-01", "F-01"): "10002345",
                ("SMT-02", "R-01"): "10002346",
            },
        )
        self.session = ScanSession(configuration)

    def test_accepts_station_material_sequence_and_resolves_device(self) -> None:
        station = self.session.handle_scan("F-01")

        self.assertTrue(station.accepted)
        self.assertEqual(ScanStep.MATERIAL, station.next_step)
        self.assertEqual("SMT-01", self.session.current_device)
        self.assertEqual("F-01", self.session.current_station)

        material = self.session.handle_scan("10002345")

        self.assertTrue(material.accepted)
        self.assertEqual(ScanStep.STATION, material.next_step)

    def test_rejects_material_while_waiting_for_station(self) -> None:
        outcome = self.session.handle_scan("10002345")

        self.assertFalse(outcome.accepted)
        self.assertEqual(ScanStep.STATION, outcome.next_step)

    def test_rejects_device_code_because_device_scan_is_removed(self) -> None:
        outcome = self.session.handle_scan("SMT-01")

        self.assertFalse(outcome.accepted)
        self.assertEqual(ScanStep.STATION, outcome.next_step)

    def test_resolves_each_globally_unique_station_to_its_device(self) -> None:
        station = self.session.handle_scan("R-01")

        self.assertTrue(station.accepted)
        self.assertEqual("SMT-02", self.session.current_device)
        self.assertEqual(ScanStep.MATERIAL, station.next_step)

    def test_retains_station_after_failed_material_verification(self) -> None:
        self.session.handle_scan("F-01")

        outcome = self.session.handle_scan("WRONG")

        self.assertTrue(outcome.accepted)
        self.assertEqual(ScanStep.MATERIAL, outcome.next_step)
        self.assertEqual("SMT-01", self.session.current_device)
        self.assertEqual("F-01", self.session.current_station)

    def test_rejects_ambiguous_configuration_station_code(self) -> None:
        session = ScanSession(
            ProductConfiguration(
                product_code="501000087",
                version="V1",
                assignments={
                    ("SMT-01", "F-01"): "10002345",
                    ("SMT-02", "F-01"): "10002346",
                },
            )
        )

        with self.assertRaisesRegex(ValueError, "not globally unique"):
            session.handle_scan("F-01")


if __name__ == "__main__":
    unittest.main()
