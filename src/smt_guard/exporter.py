"""CSV export for verification attempt records."""

import csv
from pathlib import Path
from typing import Protocol

from smt_guard.records import Attempt


class AttemptReader(Protocol):
    """Read-only boundary required by the CSV exporter."""

    def list_for_run(self, run_id: str) -> list[Attempt]:
        """Return immutable attempts for one run."""
        ...


class CsvRecordExporter:
    """Export run records in an Excel-compatible UTF-8 CSV format."""

    HEADERS = (
        "记录编号",
        "时间",
        "运行编号",
        "产品编码",
        "产品版本",
        "设备编码",
        "站位编码",
        "要求物料",
        "扫码物料",
        "结果",
        "重复检查",
    )

    def __init__(self, repository: AttemptReader) -> None:
        self._repository = repository

    def export_run(self, run_id: str, path: Path) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer: csv.DictWriter[str] = csv.DictWriter(stream, fieldnames=self.HEADERS)
            writer.writeheader()
            for attempt in self._repository.list_for_run(run_id):
                writer.writerow(self._to_row(attempt))

    @staticmethod
    def _to_row(attempt: Attempt) -> dict[str, object]:
        row: dict[str, object] = {
            "记录编号": attempt.id if attempt.id is not None else "",
            "时间": attempt.timestamp.isoformat(),
            "运行编号": attempt.run_id,
            "产品编码": attempt.product_code,
            "产品版本": attempt.product_version,
            "设备编码": attempt.device_code,
            "站位编码": attempt.station_code,
            "要求物料": attempt.expected_material,
            "扫码物料": attempt.scanned_material,
            "结果": attempt.result.value,
            "重复检查": CsvRecordExporter._yes_no(attempt.repeated),
        }
        return {column: CsvRecordExporter._safe_cell(value) for column, value in row.items()}

    @staticmethod
    def _safe_cell(value: object) -> object:
        if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
            return f"'{value}"
        return value

    @staticmethod
    def _yes_no(value: bool) -> str:
        return "是" if value else "否"
