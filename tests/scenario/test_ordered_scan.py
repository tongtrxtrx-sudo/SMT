import unittest

from smt_guard.scan import ProductConfiguration, ScanSession, ScanStep


class OrderedScanTests(unittest.TestCase):
    def setUp(self) -> None:
        configuration = ProductConfiguration(
            product_code="501000087",
            version="V1",
            assignments={
                ("SMT-01", "F-01"): "10002345",
                ("SMT-01", "F-02"): "10002346",
            },
        )
        self.session = ScanSession(configuration)

    def test_accepts_device_station_material_sequence(self) -> None:
        device = self.session.handle_scan("SMT-01")
        station = self.session.handle_scan("F-01")
        material = self.session.handle_scan("10002345")

        self.assertTrue(device.accepted)
        self.assertEqual(ScanStep.STATION, device.next_step)
        self.assertTrue(station.accepted)
        self.assertEqual(ScanStep.MATERIAL, station.next_step)
        self.assertTrue(material.accepted)
        self.assertEqual(ScanStep.STATION, material.next_step)

    def test_rejects_material_while_waiting_for_device(self) -> None:
        outcome = self.session.handle_scan("10002345")

        self.assertFalse(outcome.accepted)
        self.assertEqual(ScanStep.DEVICE, outcome.next_step)

    def test_rejects_station_before_device(self) -> None:
        outcome = self.session.handle_scan("F-01")

        self.assertFalse(outcome.accepted)
        self.assertEqual(ScanStep.DEVICE, outcome.next_step)

    def test_rejects_device_not_used_by_configuration(self) -> None:
        outcome = self.session.handle_scan("SMT-99")

        self.assertFalse(outcome.accepted)
        self.assertEqual(ScanStep.DEVICE, outcome.next_step)

    def test_rejects_station_not_belonging_to_selected_device(self) -> None:
        self.session.handle_scan("SMT-01")

        outcome = self.session.handle_scan("F-99")

        self.assertFalse(outcome.accepted)
        self.assertEqual(ScanStep.STATION, outcome.next_step)

    def test_retains_device_after_material_verification(self) -> None:
        self.session.handle_scan("SMT-01")
        self.session.handle_scan("F-01")
        self.session.handle_scan("10002345")

        outcome = self.session.handle_scan("F-02")

        self.assertTrue(outcome.accepted)
        self.assertEqual(ScanStep.MATERIAL, outcome.next_step)

    def test_can_switch_to_another_configured_device_after_verification(self) -> None:
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
        session.handle_scan("SMT-01")
        session.handle_scan("F-01")
        session.handle_scan("10002345")

        switched = session.handle_scan("SMT-02")
        station = session.handle_scan("F-01")

        self.assertTrue(switched.accepted)
        self.assertEqual(ScanStep.STATION, switched.next_step)
        self.assertTrue(station.accepted)
        self.assertEqual(ScanStep.MATERIAL, station.next_step)


if __name__ == "__main__":
    unittest.main()
