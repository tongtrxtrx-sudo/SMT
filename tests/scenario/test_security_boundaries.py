import csv
import sqlite3
import unittest
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from smt_guard.exporter import CsvRecordExporter
from smt_guard.records import Attempt, InMemoryAttemptRepository
from smt_guard.sqlite import SqliteAttemptRepository, SqliteDatabase
from smt_guard.verification import VerificationResult
from smt_guard.xlsx_reader import WorkbookLimits, WorkbookReadError, validate_workbook_archive


def attempt_with_text(run_id: str, scanned_material: str) -> Attempt:
    return Attempt(
        id=None,
        timestamp=datetime(2026, 7, 11, 12, 0, tzinfo=UTC),
        run_id=run_id,
        product_code="501000087",
        product_version="V1",
        device_code="SMT-01",
        station_code="F-01",
        expected_material="013000081",
        scanned_material=scanned_material,
        result=VerificationResult.NG,
        repeated=False,
    )


class SecurityBoundaryTests(unittest.TestCase):
    def test_csv_neutralizes_formula_text_and_preserves_normal_code(self) -> None:
        repository = InMemoryAttemptRepository()
        repository.append(attempt_with_text("=RUN()", "=HYPERLINK(\"bad\")"))

        with TemporaryDirectory() as directory:
            path = Path(directory) / "records.csv"
            CsvRecordExporter(repository).export_run("=RUN()", path)
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                row = next(csv.DictReader(stream))

        self.assertEqual("'=RUN()", row["作业号"])
        self.assertEqual("'=RUN()", row["内部运行编号"])
        self.assertEqual("'=HYPERLINK(\"bad\")", row["扫码物料"])
        self.assertEqual("013000081", row["要求物料"])

    def test_rejects_non_xlsx_path(self) -> None:
        with self.assertRaises(WorkbookReadError) as caught:
            validate_workbook_archive(Path("stations.csv"))

        self.assertIn(".xlsx", str(caught.exception))

    def test_rejects_archive_over_injected_uncompressed_limit(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "oversized.xlsx"
            with ZipFile(path, "w") as archive:
                archive.writestr("xl/worksheets/sheet1.xml", "12345678901")

            with self.assertRaises(WorkbookReadError) as caught:
                validate_workbook_archive(
                    path,
                    limits=WorkbookLimits(
                        max_archive_bytes=1024,
                        max_uncompressed_bytes=10,
                        max_compression_ratio=1000,
                    ),
                )

        self.assertIn("uncompressed", str(caught.exception))

    def test_sql_like_run_identifier_round_trips_without_schema_change(self) -> None:
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        SqliteDatabase(connection).initialize()
        repository = SqliteAttemptRepository(connection)
        malicious = "RUN'; DROP TABLE attempts;--"
        repository.append(attempt_with_text(malicious, "013000081"))

        records = repository.list_for_run(malicious)
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'attempts'"
        ).fetchone()

        self.assertEqual(malicious, records[0].run_id)
        self.assertEqual(("attempts",), table)

    def test_release_script_declares_all_quality_and_security_gates(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        script = (project_root / "scripts" / "verify_release.ps1").read_text("utf-8")

        for command in (
            "pytest --cov",
            "ruff check",
            "pyright",
            "bandit -r src",
            "pip-audit",
            "build_windows.ps1",
            "SMTGuard.exe",
            "--smoke-test",
        ):
            with self.subTest(command=command):
                self.assertIn(command, script)


if __name__ == "__main__":
    unittest.main()
