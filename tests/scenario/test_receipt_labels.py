import os
import re
import shutil
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics

from smt_guard.receipt_label_app import main
from smt_guard.receipt_labels import (
    LabelRequest,
    ReceiptImportError,
    ReceiptLabelExportError,
    ReceiptLabelPdfExporter,
    ReceiptLabelWorkspaceSettings,
    ReceiptWorkbookImporter,
)
from smt_guard.ui.receipt_labels import ReceiptLabelWindow

HEADERS = (
    "采购入库单号",
    "仓库",
    "入库日期",
    "收货人",
    "商品名",
    "商品编号",
    "商品规格",
    "入库数量",
    "商品单位",
    "加工单号",
)

LONG_SPECIFICATION = (
    "SX-SLH 621 HT16P153 SOT23-6 HT251024 v2.1 Cs 0xF917 0x9259EHC300 "
    "校验码:0xF917 0x9259 ENC300功能是:高-低-关〈高、低档都有放!电曲线,"
    "长按调光，双击爆闪》。"
)


class ReceiptLabelPdfExporterForTest(ReceiptLabelPdfExporter):
    """Expose label text layout details for focused regression assertions."""

    def fit_specification_for_test(
        self,
        specification: str,
    ) -> tuple[tuple[str, ...], float, str]:
        self._font_name = self._register_font()
        lines, font_size = self._fit_text_lines(
            f"规格：{specification}",
            self._font_name,
            preferred_font_size=6.8,
            minimum_font_size=4.8,
            max_width=self.PAGE_WIDTH - 5 * mm,
            max_lines=4,
        )
        return lines, font_size, self._font_name


def write_receipt(
    path: Path,
    *,
    second_receipt: bool = False,
    first_specification: str = "立式 6P 贴片",
) -> None:
    workbook = Workbook()
    sheet = cast(Worksheet, workbook.active)
    sheet.title = "Worksheet"
    sheet.append(HEADERS)
    sheet.append(
        (
            "CGRK20260722001",
            "电子原材料仓",
            "2026-07-22",
            "陈肖楠",
            "Type-C",
            15000009,
            first_specification,
            150300,
            "个",
            "20260707-1",
        )
    )
    sheet.cell(2, 6).number_format = "000000000"
    sheet.append(
        (
            "CGRK20260722002" if second_receipt else "CGRK20260722001",
            "电子原材料仓",
            "2026-07-22",
            "陈肖楠",
            "电阻",
            "005000095",
            "0603-510R-±5%",
            75000,
            "个",
            "20260707-1",
        )
    )
    workbook.save(path)
    workbook.close()


class ReceiptLabelsTests(unittest.TestCase):
    app: QApplication

    @classmethod
    def setUpClass(cls) -> None:
        application = QApplication.instance()
        cls.app = application if isinstance(application, QApplication) else QApplication([])

    def test_imports_receipt_by_headers_and_preserves_leading_zeroes(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "receipt.xlsx"
            write_receipt(source)

            document = ReceiptWorkbookImporter().import_file(source)

            self.assertEqual("CGRK20260722001", document.receipt_number)
            self.assertEqual("电子原材料仓", document.warehouse)
            self.assertEqual("2026-07-22", document.receipt_date)
            self.assertEqual("陈肖楠", document.receiver)
            self.assertEqual("20260707-1", document.process_number)
            self.assertEqual(2, len(document.items))
            self.assertEqual("015000009", document.items[0].material_code)
            self.assertEqual("005000095", document.items[1].material_code)

    def test_rejects_multiple_receipt_numbers_in_one_file(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "receipt.xlsx"
            write_receipt(source, second_receipt=True)

            with self.assertRaisesRegex(ReceiptImportError, "多个采购入库单号"):
                ReceiptWorkbookImporter().import_file(source)

    def test_exports_one_60_by_40_pdf_per_material(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "receipt.xlsx"
            target = root / "workspace"
            write_receipt(source)
            document = ReceiptWorkbookImporter().import_file(source)

            result = ReceiptLabelPdfExporter().export(
                (LabelRequest(document.items[0]), LabelRequest(document.items[1])),
                target,
            )

            self.assertEqual(2, result.label_count)
            self.assertEqual(
                ReceiptLabelPdfExporter.DEFAULT_LABEL_FORMAT_ID,
                result.label_format_id,
            )
            self.assertEqual(2, result.generated_count)
            self.assertEqual(0, result.reused_count)
            self.assertEqual(target, result.workspace_root)
            self.assertEqual(target / "标签库", result.library_directory)
            self.assertEqual(target / "当前打印", result.current_print_directory)
            self.assertEqual(result.current_print_directory, result.output_directory)
            self.assertEqual(
                {"物料-015000009.pdf", "物料-005000095.pdf"},
                {file.output_path.name for file in result.files},
            )
            for file in result.files:
                self.assertTrue(file.library_path.is_file())
                self.assertEqual(file.library_path.read_bytes(), file.output_path.read_bytes())
                data = file.output_path.read_bytes()
                self.assertTrue(data.startswith(b"%PDF"))
                media_box = re.search(
                    rb"/MediaBox\s*\[\s*0\s+0\s+([0-9.]+)\s+([0-9.]+)\s*\]",
                    data,
                )
                self.assertIsNotNone(media_box)
                assert media_box is not None
                self.assertAlmostEqual(170.0787, float(media_box.group(1)), places=2)
                self.assertAlmostEqual(113.3858, float(media_box.group(2)), places=2)

    def test_exposes_one_expandable_label_format_and_rejects_unknown_format(self) -> None:
        formats = ReceiptLabelPdfExporter.available_formats()

        self.assertEqual(1, len(formats))
        self.assertEqual(
            ReceiptLabelPdfExporter.DEFAULT_LABEL_FORMAT_ID,
            formats[0].format_id,
        )
        self.assertEqual(60, formats[0].page_width_mm)
        self.assertEqual(40, formats[0].page_height_mm)
        self.assertEqual("Code 128", formats[0].barcode_type)
        self.assertIn("60 × 40 mm", formats[0].display_name)
        self.assertIn("Code 128", formats[0].display_name)

        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "receipt.xlsx"
            write_receipt(source)
            document = ReceiptWorkbookImporter().import_file(source)

            with self.assertRaisesRegex(ReceiptLabelExportError, "不支持的标签格式"):
                ReceiptLabelPdfExporter().export(
                    (LabelRequest(document.items[0]),),
                    root / "workspace",
                    label_format_id="unknown-format",
                )

            self.assertFalse((root / "workspace").exists())

    def test_long_specification_fits_without_ellipsis_or_lost_content(self) -> None:
        exporter = ReceiptLabelPdfExporterForTest()
        lines, font_size, font_name = exporter.fit_specification_for_test(
            LONG_SPECIFICATION,
        )

        self.assertLessEqual(len(lines), 4)
        self.assertGreaterEqual(font_size, 4.8)
        self.assertGreater(
            exporter.MATERIAL_CODE_BASELINE - exporter.SPECIFICATION_FIRST_BASELINE,
            3.5 * mm,
        )
        self.assertNotIn("…", "".join(lines))
        self.assertTrue(any("HT251024" in line for line in lines))
        self.assertEqual(
            re.sub(r"\s+", "", "".join(lines)),
            re.sub(r"\s+", "", f"规格：{LONG_SPECIFICATION}"),
        )
        self.assertTrue(
            all(
                pdfmetrics.stringWidth(line, font_name, font_size)
                <= exporter.PAGE_WIDTH - 5 * mm
                for line in lines
            )
        )

    def test_reuses_unchanged_material_files_and_refreshes_changed_content(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "receipt.xlsx"
            target = root / "workspace"
            write_receipt(source)
            document = ReceiptWorkbookImporter().import_file(source)
            exporter = ReceiptLabelPdfExporter()
            requests = tuple(LabelRequest(item) for item in document.items)

            first = exporter.export(requests, target)
            original_bytes = {
                result.item.material_code: result.library_path.read_bytes()
                for result in first.files
            }
            second = exporter.export(
                tuple(LabelRequest(replace(item, quantity="999999")) for item in document.items),
                target,
            )

            self.assertEqual(0, second.generated_count)
            self.assertEqual(2, second.reused_count)
            self.assertTrue(all(result.reused for result in second.files))

            changed_item = replace(document.items[1], specification="0603-510R-±1%")
            third = exporter.export(
                (LabelRequest(document.items[0]), LabelRequest(changed_item)),
                target,
            )

            self.assertEqual(1, third.generated_count)
            self.assertEqual(1, third.reused_count)
            current_bytes = {
                result.item.material_code: result.library_path.read_bytes()
                for result in third.files
            }
            self.assertEqual(
                original_bytes[document.items[0].material_code],
                current_bytes[document.items[0].material_code],
            )
            self.assertNotEqual(
                original_bytes[document.items[1].material_code],
                current_bytes[document.items[1].material_code],
            )
            self.assertEqual(
                {"物料-015000009.pdf", "物料-005000095.pdf"},
                {path.name for path in third.current_print_directory.glob("*.pdf")},
            )

            fourth = exporter.export((LabelRequest(document.items[0]),), target)

            self.assertEqual(
                {"物料-015000009.pdf"},
                {path.name for path in fourth.current_print_directory.glob("*.pdf")},
            )
            self.assertTrue((target / "标签库" / "物料-005000095.pdf").is_file())

    def test_startup_clears_managed_current_print_and_preserves_library(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            settings = ReceiptLabelWorkspaceSettings(
                root / "settings.json",
                workspace,
            )
            settings.save_workspace_root(workspace)
            exporter = ReceiptLabelPdfExporter()
            paths = exporter.prepare_workspace(workspace, clear_current_print=False)
            library_file = paths.library_directory / "keep.pdf"
            current_pdf = paths.current_print_directory / "old.pdf"
            current_note = paths.current_print_directory / "old.txt"
            library_file.write_bytes(b"library")
            current_pdf.write_bytes(b"old")
            current_note.write_text("old", encoding="utf-8")

            window = ReceiptLabelWindow(
                exporter=exporter,
                workspace_settings=settings,
            )
            self.addCleanup(window.close)

            self.assertEqual(workspace.resolve(), settings.load_workspace_root())
            self.assertTrue(library_file.is_file())
            self.assertFalse(current_pdf.exists())
            self.assertFalse(current_note.exists())
            self.assertEqual([], list(paths.current_print_directory.iterdir()))
            self.assertTrue((workspace / exporter.WORKSPACE_MARKER).is_file())

    def test_legacy_documents_default_moves_to_desktop_and_is_recreated(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            desktop_workspace = root / "Desktop" / "SMT物料标签"
            legacy_workspace = root / "Documents" / "SMT物料标签"
            settings_path = root / "settings.json"
            settings_path.write_text(
                "{\n"
                '  "settings_version": 1,\n'
                f'  "workspace_root": "{str(legacy_workspace).replace(chr(92), chr(92) * 2)}"\n'
                "}\n",
                encoding="utf-8",
            )
            settings = ReceiptLabelWorkspaceSettings(
                settings_path,
                desktop_workspace,
            )

            first_window = ReceiptLabelWindow(workspace_settings=settings)
            first_window.close()

            self.assertEqual(desktop_workspace.resolve(), settings.load_workspace_root())
            self.assertTrue((desktop_workspace / "标签库").is_dir())
            self.assertTrue((desktop_workspace / "当前打印").is_dir())
            shutil.rmtree(desktop_workspace)

            second_window = ReceiptLabelWindow(workspace_settings=settings)
            self.addCleanup(second_window.close)

            self.assertTrue((desktop_workspace / "标签库").is_dir())
            self.assertTrue((desktop_workspace / "当前打印").is_dir())
            self.assertEqual([], list((desktop_workspace / "当前打印").iterdir()))

    def test_refuses_to_clear_an_unmarked_nonempty_current_print_folder(self) -> None:
        with TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            current = workspace / "当前打印"
            current.mkdir(parents=True)
            personal_file = current / "personal.txt"
            personal_file.write_text("do not delete", encoding="utf-8")

            with self.assertRaisesRegex(ReceiptLabelExportError, "为防止误删"):
                ReceiptLabelPdfExporter().prepare_workspace(
                    workspace,
                    clear_current_print=True,
                )

            self.assertEqual("do not delete", personal_file.read_text(encoding="utf-8"))

    def test_window_defaults_to_all_items_and_exports_selected_materials(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "receipt.xlsx"
            target = root / "workspace"
            write_receipt(source)
            settings = ReceiptLabelWorkspaceSettings(
                root / "settings.json",
                target,
            )
            window = ReceiptLabelWindow(workspace_settings=settings)
            self.addCleanup(window.close)

            window.load_receipt(source)
            window.set_row_selected(0, False)
            result = window.export_labels(target)

            self.assertEqual(2, window.table.rowCount())
            self.assertEqual(1, result.label_count)
            self.assertEqual(
                {"物料-005000095.pdf"},
                {path.name for path in result.current_print_directory.glob("*.pdf")},
            )
            status_item = window.table.item(1, 4)
            self.assertIsNotNone(status_item)
            assert status_item is not None
            self.assertEqual("可复用", status_item.text())
            self.assertTrue(window.export_button.isEnabled())
            self.assertIn("1 个", window.export_button.text())
            self.assertEqual("success", window.status_label.property("feedbackState"))

    def test_excel_picker_opens_on_desktop_by_default(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            desktop = root / "Desktop"
            settings = ReceiptLabelWorkspaceSettings(
                root / "settings.json",
                desktop / "SMT物料标签",
            )
            window = ReceiptLabelWindow(workspace_settings=settings)
            self.addCleanup(window.close)

            with patch(
                "smt_guard.ui.receipt_labels.QFileDialog.getOpenFileName",
                return_value=("", ""),
            ) as get_open_file_name:
                window.browse_button.click()

            self.assertEqual(str(desktop.resolve()), get_open_file_name.call_args.args[2])

    def test_window_shows_default_label_format_selector(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            settings = ReceiptLabelWorkspaceSettings(
                root / "settings.json",
                root / "workspace",
            )
            window = ReceiptLabelWindow(workspace_settings=settings)
            self.addCleanup(window.close)

            self.assertEqual(1, window.label_format_combo.count())
            self.assertEqual(
                ReceiptLabelPdfExporter.DEFAULT_LABEL_FORMAT_ID,
                window.label_format_combo.currentData(),
            )
            self.assertIn("60 × 40 mm", window.label_format_combo.currentText())
            self.assertIn("Code 128", window.label_format_combo.currentText())

    def test_window_wraps_long_specification_and_keeps_full_tooltip(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "receipt.xlsx"
            write_receipt(source, first_specification=LONG_SPECIFICATION)
            settings = ReceiptLabelWorkspaceSettings(
                root / "settings.json",
                root / "workspace",
            )
            window = ReceiptLabelWindow(workspace_settings=settings)
            self.addCleanup(window.close)
            window.resize(1220, 760)
            window.load_receipt(source)
            self.app.processEvents()

            specification_item = window.table.item(0, 3)
            self.assertIsNotNone(specification_item)
            assert specification_item is not None
            self.assertEqual(LONG_SPECIFICATION, specification_item.text())
            self.assertEqual(LONG_SPECIFICATION, specification_item.toolTip())
            self.assertEqual(Qt.TextElideMode.ElideNone, window.table.textElideMode())
            self.assertGreater(window.table.rowHeight(0), 42)

    def test_compact_window_keeps_prepare_action_in_visible_table_footer(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "receipt.xlsx"
            write_receipt(source)
            settings = ReceiptLabelWorkspaceSettings(
                root / "settings.json",
                root / "workspace",
            )
            window = ReceiptLabelWindow(workspace_settings=settings)
            self.addCleanup(window.close)
            window.load_receipt(source)

            self.assertIs(
                window.select_all_button.parentWidget(),
                window.export_button.parentWidget(),
            )
            self.assertLessEqual(window.minimumSizeHint().height(), 760)

    def test_standalone_entry_has_non_visible_smoke_mode(self) -> None:
        exit_code = main(["--smoke-test"])

        self.assertEqual(0, exit_code)
        self.assertFalse(any(widget.isVisible() for widget in self.app.topLevelWidgets()))

    def test_standalone_packaging_and_readme_are_declared(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        spec = (project_root / "packaging" / "SMTReceiptLabels.spec").read_text("utf-8")
        script = (project_root / "scripts" / "build_receipt_labels.ps1").read_text("utf-8")
        readme = (project_root / "README.md").read_text("utf-8")

        self.assertIn('name="SMTReceiptLabels"', spec)
        self.assertIn("console=False", spec)
        self.assertIn("packaging/SMTReceiptLabels.spec", script.replace("\\", "/"))
        self.assertIn("smt-receipt-labels", readme)
        self.assertIn("build_receipt_labels.ps1", readme)
        self.assertIn("60 × 40 mm", readme)
        self.assertIn("直接复用", readme)


if __name__ == "__main__":
    unittest.main()
