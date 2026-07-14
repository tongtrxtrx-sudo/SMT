import unittest
from pathlib import Path
from typing import Any

from smt_guard.xlsx_reader import OpenpyxlWorkbookReader, WorkbookReadError


class FakeWorksheet:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self._rows = rows

    def iter_rows(self, *, values_only: bool) -> list[tuple[object, ...]]:
        if not values_only:
            raise AssertionError("Reader must request cell values")
        return self._rows


class FakeWorkbook:
    def __init__(self, sheets: dict[str, FakeWorksheet]) -> None:
        self._sheets = sheets
        self.closed = False

    @property
    def sheetnames(self) -> list[str]:
        return list(self._sheets)

    def __getitem__(self, name: str) -> FakeWorksheet:
        return self._sheets[name]

    def close(self) -> None:
        self.closed = True


class RecordingLoader:
    def __init__(self, workbook: FakeWorkbook) -> None:
        self.workbook = workbook
        self.calls: list[tuple[Path, dict[str, Any]]] = []

    def __call__(self, path: Path, **options: Any) -> FakeWorkbook:
        self.calls.append((path, options))
        return self.workbook


class OpenpyxlWorkbookReaderTests(unittest.TestCase):
    def test_reads_rows_in_safe_mode_and_preserves_text_codes(self) -> None:
        workbook = FakeWorkbook(
            {
                "Worksheet": FakeWorksheet(
                    [
                        (" 商品编号 ", "商品名", "备注"),
                        (" 013000081 ", " 端子线 ", None),
                        (None, None, None),
                        ("005000103", "贴片电阻", ""),
                    ]
                )
            }
        )
        loader = RecordingLoader(workbook)
        reader = OpenpyxlWorkbookReader(workbook_loader=loader)

        rows = reader.read_sheet(Path("商品BOM_导出.xlsx"), "Worksheet")

        self.assertEqual(
            [
                {"商品编号": "013000081", "商品名": "端子线", "备注": "", "_row_number": 2},
                {
                    "商品编号": "005000103",
                    "商品名": "贴片电阻",
                    "备注": "",
                    "_row_number": 4,
                },
            ],
            rows,
        )
        self.assertEqual(
            [(Path("商品BOM_导出.xlsx"), {"read_only": True, "data_only": True})],
            loader.calls,
        )
        self.assertTrue(workbook.closed)

    def test_reports_missing_sheet_and_closes_workbook(self) -> None:
        workbook = FakeWorkbook({"Other": FakeWorksheet([("A",), ("value",)])})
        reader = OpenpyxlWorkbookReader(workbook_loader=RecordingLoader(workbook))

        with self.assertRaises(WorkbookReadError) as caught:
            reader.read_sheet(Path("bom.xlsx"), "Worksheet")

        self.assertIn("Worksheet", str(caught.exception))
        self.assertIn("Other", str(caught.exception))
        self.assertTrue(workbook.closed)

    def test_rejects_ambiguous_headers_and_closes_workbook(self) -> None:
        invalid_headers = [
            ("商品编号", " "),
            ("商品编号", "商品编号"),
        ]

        for headers in invalid_headers:
            with self.subTest(headers=headers):
                workbook = FakeWorkbook({"Worksheet": FakeWorksheet([headers, ("001", "x")])})
                reader = OpenpyxlWorkbookReader(workbook_loader=RecordingLoader(workbook))

                with self.assertRaises(WorkbookReadError):
                    reader.read_sheet(Path("bom.xlsx"), "Worksheet")

                self.assertTrue(workbook.closed)


if __name__ == "__main__":
    unittest.main()
