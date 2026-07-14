import csv
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from smt_guard.exporter import CsvRecordExporter
from smt_guard.records import Attempt, InMemoryAttemptRepository
from smt_guard.verification import VerificationResult


def make_attempt(run_id: str, station: str = "F-01") -> Attempt:
    return Attempt(
        id=None,
        timestamp=datetime(2026, 7, 11, 10, 0, tzinfo=UTC),
        run_id=run_id,
        product_code="501000087",
        product_version="V1",
        device_code="SMT-01",
        station_code=station,
        expected_material="013000081",
        scanned_material='013000081,"测试"',
        result=VerificationResult.OK,
        repeated=False,
    )


class RecordExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = InMemoryAttemptRepository()
        self.exporter = CsvRecordExporter(self.repository)

    def test_exports_utf8_bom_and_stable_headers(self) -> None:
        self.repository.append(make_attempt("RUN-1"))

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.csv"
            self.exporter.export_run("RUN-1", path)
            raw = path.read_bytes()
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))

        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(1, len(rows))
        self.assertEqual("013000081", rows[0]["要求物料"])

    def test_empty_run_exports_headers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.csv"
            self.exporter.export_run("EMPTY", path)
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                reader = csv.reader(stream)
                rows = list(reader)

        self.assertEqual(1, len(rows))
        self.assertIn("运行编号", rows[0])
        self.assertIn("结果", rows[0])

    def test_special_text_is_quoted_and_round_trips(self) -> None:
        self.repository.append(make_attempt("RUN-1"))

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.csv"
            self.exporter.export_run("RUN-1", path)
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                row = next(csv.DictReader(stream))

        self.assertEqual('013000081,"测试"', row["扫码物料"])

    def test_export_is_isolated_to_selected_run(self) -> None:
        self.repository.append(make_attempt("RUN-1", "F-01"))
        self.repository.append(make_attempt("RUN-2", "F-02"))

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.csv"
            self.exporter.export_run("RUN-1", path)
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))

        self.assertEqual(1, len(rows))
        self.assertEqual("RUN-1", rows[0]["运行编号"])
        self.assertEqual("F-01", rows[0]["站位编码"])


if __name__ == "__main__":
    unittest.main()
