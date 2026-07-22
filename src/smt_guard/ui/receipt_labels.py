"""Standalone purchase-receipt label workflow."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from smt_guard.receipt_labels import (
    LabelExportResult,
    LabelRequest,
    ReceiptDocument,
    ReceiptImportError,
    ReceiptItem,
    ReceiptLabelExportError,
    ReceiptLabelPdfExporter,
    ReceiptLabelWorkspaceSettings,
    ReceiptWorkbookImporter,
)

RECEIPT_LABEL_STYLE = """
QWidget {
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
    font-size: 14px;
    color: #1d2939;
    background-color: #f4f7fb;
}
QMainWindow { background-color: #f4f7fb; }
QFrame#contentCard {
    background-color: #ffffff;
    border: 1px solid #dbe4f0;
    border-radius: 12px;
}
QLabel#pageTitle {
    color: #102a56;
    font-size: 25px;
    font-weight: 700;
}
QLabel#pageSubtitle, QLabel#hintLabel { color: #667085; }
QLabel#sectionTitle {
    color: #344054;
    font-size: 16px;
    font-weight: 700;
}
QLabel[summaryChip="true"] {
    color: #175cd3;
    background-color: #eff8ff;
    border: 1px solid #b2ddff;
    border-radius: 8px;
    padding: 8px 12px;
    font-weight: 600;
}
QLineEdit, QComboBox, QTableWidget {
    color: #1d2939;
    background-color: #ffffff;
    border: 1px solid #c7d2e0;
    border-radius: 7px;
    selection-background-color: #dcecff;
    selection-color: #102a56;
}
QLineEdit, QComboBox { padding: 8px 10px; }
QLineEdit:focus, QComboBox:focus { border: 2px solid #2e90fa; }
QTableWidget {
    alternate-background-color: #f7f9fc;
    gridline-color: #e4e7ec;
}
QTableWidget::item { padding: 7px 8px; }
QHeaderView::section {
    color: #344054;
    background-color: #eef3f8;
    border: 0;
    border-right: 1px solid #dbe4f0;
    border-bottom: 1px solid #dbe4f0;
    padding: 9px 7px;
    font-weight: 700;
}
QPushButton {
    min-height: 35px;
    padding: 6px 16px;
    color: #344054;
    background-color: #ffffff;
    border: 1px solid #aebdce;
    border-radius: 7px;
    font-weight: 600;
}
QPushButton:hover { background-color: #f0f5fb; }
QPushButton[actionRole="primary"] {
    color: #ffffff;
    background-color: #175cd3;
    border-color: #175cd3;
}
QPushButton[actionRole="primary"]:hover { background-color: #1849a9; }
QPushButton[actionRole="success"] {
    color: #ffffff;
    background-color: #12b76a;
    border-color: #12b76a;
}
QPushButton[actionRole="success"]:hover { background-color: #039855; }
QPushButton:disabled {
    color: #667085;
    background-color: #d0d5dd;
    border-color: #d0d5dd;
}
"""


def register_windows_fonts(font_directory: Path | None = None) -> None:
    """Register installed Chinese UI fonts, including with Qt's offscreen plugin."""
    directory = (
        font_directory
        if font_directory is not None
        else Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    )
    for filename in ("msyh.ttc", "msyhbd.ttc"):
        path = directory / filename
        if path.is_file():
            QFontDatabase.addApplicationFont(str(path))


class ReceiptLabelWindow(QMainWindow):
    """Import one receipt and maintain reusable material-label PDF files."""

    HEADERS = ("生成", "商品编号", "商品名", "规格", "文件状态")

    def __init__(
        self,
        importer: ReceiptWorkbookImporter | None = None,
        exporter: ReceiptLabelPdfExporter | None = None,
        workspace_settings: ReceiptLabelWorkspaceSettings | None = None,
    ) -> None:
        super().__init__()
        self.importer = importer or ReceiptWorkbookImporter()
        self.exporter = exporter or ReceiptLabelPdfExporter()
        self.workspace_settings = workspace_settings or ReceiptLabelWorkspaceSettings()
        self.workspace_root = self.workspace_settings.load_workspace_root()
        self.document: ReceiptDocument | None = None
        self._items: list[ReceiptItem] = []
        self._selection_boxes: list[QCheckBox] = []

        register_windows_fonts()
        self.setWindowTitle("SMT 物料标签库")
        self.resize(1220, 820)
        font = QFont()
        font.setFamilies(("Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI"))
        font.setPointSize(10)
        self.setFont(font)
        self.setStyleSheet(RECEIPT_LABEL_STYLE)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        title = QLabel("物料标签库")
        title.setObjectName("pageTitle")
        subtitle = QLabel("标签永久保存在标签库；本次选择会复制到当前打印，方便直接批量打印。")
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        import_card = self._card()
        import_layout = QVBoxLayout(import_card)
        import_layout.setContentsMargins(14, 12, 14, 12)
        import_layout.setSpacing(9)
        import_title = QLabel("1  选择入库单和工作目录")
        import_title.setObjectName("sectionTitle")
        import_layout.addWidget(import_title)
        file_row = QHBoxLayout()
        self.file_input = QLineEdit()
        self.file_input.setReadOnly(True)
        self.file_input.setPlaceholderText("请选择采购入库单 Excel 文件（.xlsx）")
        self.file_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.browse_button = QPushButton("选择 Excel")
        self.browse_button.setProperty("actionRole", "primary")
        self.browse_button.clicked.connect(self._choose_file)
        file_row.addWidget(self.file_input, 1)
        file_row.addWidget(self.browse_button)
        import_layout.addLayout(file_row)

        folder_row = QHBoxLayout()
        self.output_directory_input = QLineEdit()
        self.output_directory_input.setReadOnly(True)
        self.output_directory_input.setPlaceholderText("请选择标签工作目录")
        self.output_directory_input.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.choose_output_directory_button = QPushButton("选择工作目录")
        self.choose_output_directory_button.clicked.connect(self._choose_output_directory)
        folder_row.addWidget(self.output_directory_input, 1)
        folder_row.addWidget(self.choose_output_directory_button)
        import_layout.addLayout(folder_row)

        format_row = QHBoxLayout()
        format_label = QLabel("标签格式")
        self.label_format_combo = QComboBox()
        self.label_format_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.label_format_combo.setToolTip(
            "选择生成的标签尺寸与条码类型；以后新增格式会显示在这里。"
        )
        for label_format in self.exporter.available_formats():
            self.label_format_combo.addItem(
                label_format.display_name,
                label_format.format_id,
            )
        default_index = self.label_format_combo.findData(
            self.exporter.DEFAULT_LABEL_FORMAT_ID
        )
        if default_index >= 0:
            self.label_format_combo.setCurrentIndex(default_index)
        self.label_format_combo.currentIndexChanged.connect(
            self._on_label_format_changed
        )
        format_hint = QLabel("当前提供 1 种，后续可继续增加")
        format_hint.setObjectName("hintLabel")
        format_row.addWidget(format_label)
        format_row.addWidget(self.label_format_combo, 1)
        format_row.addWidget(format_hint)
        import_layout.addLayout(format_row)

        self.workspace_paths_label = QLabel()
        self.workspace_paths_label.setObjectName("hintLabel")
        self.workspace_paths_label.setWordWrap(True)
        import_layout.addWidget(self.workspace_paths_label)
        layout.addWidget(import_card)

        list_card = self._card()
        list_layout = QVBoxLayout(list_card)
        list_layout.setContentsMargins(14, 12, 14, 12)
        list_layout.setSpacing(9)
        list_header = QHBoxLayout()
        list_title = QLabel("2  核对需要生成的物料标签")
        list_title.setObjectName("sectionTitle")
        self.summary_label = QLabel("尚未导入入库单")
        self.summary_label.setProperty("summaryChip", True)
        list_header.addWidget(list_title)
        list_header.addStretch(1)
        list_header.addWidget(self.summary_label)
        list_layout.addLayout(list_header)

        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setWordWrap(True)
        self.table.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.setMinimumHeight(220)
        self.table.setShowGrid(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.sectionResized.connect(self._on_table_section_resized)
        for column, width in enumerate((66, 150, 220, 520, 150)):
            self.table.setColumnWidth(column, width)
        list_layout.addWidget(self.table, 1)

        selection_row = QHBoxLayout()
        self.select_all_button = QPushButton("全部选择")
        self.select_all_button.clicked.connect(lambda: self._set_all_selected(True))
        self.clear_button = QPushButton("取消全选")
        self.clear_button.clicked.connect(lambda: self._set_all_selected(False))
        self.status_label = QLabel("请选择一份入库单")
        self.status_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.status_label.setToolTip(
            "每次生成会替换“当前打印”内容；重复张数请在 PDF 打印窗口设置。"
        )
        self._set_status("neutral", self.status_label.text())
        self.export_button = QPushButton("准备当前打印")
        self.export_button.setProperty("actionRole", "success")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self._export_to_selected_folder)
        selection_row.addWidget(self.select_all_button)
        selection_row.addWidget(self.clear_button)
        selection_row.addWidget(self.status_label, 1)
        selection_row.addWidget(self.export_button)
        list_layout.addLayout(selection_row)
        layout.addWidget(list_card, 1)

        self.setCentralWidget(central)
        self.output_directory_input.setText(str(self.workspace_root))
        self._update_workspace_paths_label()
        try:
            paths = self.exporter.prepare_workspace(
                self.workspace_root,
                clear_current_print=True,
            )
            self.workspace_settings.save_workspace_root(paths.root)
        except ReceiptLabelExportError as error:
            self._set_status("warning", f"当前打印未自动清理：{error}")
        else:
            self._set_status(
                "neutral",
                "当前打印文件夹已清空，请选择一份采购入库单。",
            )

    @staticmethod
    def _card() -> QFrame:
        card = QFrame()
        card.setObjectName("contentCard")
        return card

    def load_receipt(self, path: Path) -> ReceiptDocument:
        """Load and display one workbook; raise a concise error when invalid."""
        document = self.importer.import_file(path)
        self.document = document
        self._items = self._deduplicate_items(document.items)
        self.file_input.setText(str(document.source_path))
        self._populate_table()
        metadata = [
            f"入库单 {document.receipt_number or '-'}",
            f"共 {len(self._items)} 种物料",
        ]
        if document.warehouse:
            metadata.append(document.warehouse)
        if document.receipt_date:
            metadata.append(document.receipt_date)
        self.summary_label.setText(" · ".join(metadata))
        self._set_status(
            "success",
            f"导入成功：已全选 {len(self._items)} 种物料；已有相同标签将直接复用。",
        )
        self._refresh_file_statuses()
        self._update_selection_state()
        return document

    @staticmethod
    def _deduplicate_items(items: tuple[ReceiptItem, ...]) -> list[ReceiptItem]:
        unique: dict[str, ReceiptItem] = {}
        for item in items:
            existing = unique.get(item.material_code)
            if existing is not None and (
                existing.material_name != item.material_name
                or existing.specification != item.specification
            ):
                raise ReceiptImportError(
                    f"商品编号 {item.material_code} 对应了不同的名称或规格，请先核对入库单"
                )
            unique.setdefault(item.material_code, item)
        return list(unique.values())

    def export_labels(self, workspace_root: Path) -> LabelExportResult:
        """Update the library and prepare current-print files without opening them."""
        if self.document is None:
            raise ReceiptLabelExportError("请先导入采购入库单")
        requests = tuple(
            LabelRequest(item)
            for item, checkbox in zip(
                self._items,
                self._selection_boxes,
                strict=True,
            )
            if checkbox.isChecked()
        )
        result = self.exporter.export(
            requests,
            workspace_root,
            label_format_id=self._selected_label_format_id(),
        )
        self.workspace_root = result.workspace_root
        self.workspace_settings.save_workspace_root(result.workspace_root)
        self.output_directory_input.setText(str(result.workspace_root))
        self._update_workspace_paths_label()
        self._set_status(
            "success",
            f"完成：新生成或更新 {result.generated_count} 个，直接复用 {result.reused_count} 个；"
            f"当前打印已准备 {result.label_count} 个文件：{result.current_print_directory}",
        )
        self._refresh_file_statuses()
        return result

    def set_row_selected(self, row: int, selected: bool) -> None:
        """Change one visible row selection for automation and keyboard workflows."""
        self._selection_boxes[row].setChecked(selected)

    def _populate_table(self) -> None:
        self.table.setRowCount(0)
        self._selection_boxes.clear()
        for row, item in enumerate(self._items):
            self.table.insertRow(row)
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(self._update_selection_state)
            check_container = QWidget()
            check_layout = QHBoxLayout(check_container)
            check_layout.setContentsMargins(0, 0, 0, 0)
            check_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            check_layout.addWidget(checkbox)
            self.table.setCellWidget(row, 0, check_container)
            self._selection_boxes.append(checkbox)

            values = (
                item.material_code,
                item.material_name,
                item.specification or "-",
                "待检查",
            )
            for column, value in enumerate(values, start=1):
                table_item = QTableWidgetItem(value)
                table_item.setToolTip(value)
                if column in (1, 4):
                    table_item.setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(row, column, table_item)
        self._resize_table_rows()

    def _resize_table_rows(self) -> None:
        """Keep short rows compact while showing wrapped specifications in full."""
        self.table.resizeRowsToContents()
        for row in range(self.table.rowCount()):
            self.table.setRowHeight(row, max(42, self.table.rowHeight(row)))

    def _on_table_section_resized(
        self,
        _logical_index: int,
        _old_size: int,
        _new_size: int,
    ) -> None:
        self._resize_table_rows()

    @Slot()
    def _choose_file(self) -> None:
        desktop_directory = self.workspace_settings.default_workspace_root.parent.resolve()
        filename, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "选择采购入库单",
            str(desktop_directory),
            "Excel 工作簿 (*.xlsx)",
        )
        if not filename:
            return
        try:
            self.load_receipt(Path(filename))
        except ReceiptImportError as error:
            self._set_status("error", str(error))

    @Slot()
    def _choose_output_directory(self) -> None:
        start_directory = self.output_directory_input.text()
        if not start_directory and self.document is not None:
            start_directory = str(self.document.source_path.parent)
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择标签工作目录（将在其中创建“标签库”和“当前打印”）",
            start_directory,
        )
        if not directory:
            return
        root = Path(directory)
        try:
            paths = self.exporter.prepare_workspace(root, clear_current_print=True)
            self.workspace_settings.save_workspace_root(paths.root)
        except ReceiptLabelExportError as error:
            self._set_status("error", str(error))
            return
        self.workspace_root = paths.root
        self.output_directory_input.setText(str(paths.root))
        self._update_workspace_paths_label()
        self._set_status("neutral", "工作目录已切换，当前打印文件夹已清空。")
        self._refresh_file_statuses()

    @Slot()
    def _export_to_selected_folder(self) -> None:
        if self.document is None:
            self._set_status("warning", "请先导入采购入库单")
            return
        directory = self.output_directory_input.text().strip()
        if not directory:
            self._set_status("warning", "请选择标签工作目录")
            return
        try:
            self.export_labels(Path(directory))
        except ReceiptLabelExportError as error:
            self._set_status("error", str(error))

    def _set_all_selected(self, selected: bool) -> None:
        for checkbox in self._selection_boxes:
            checkbox.setChecked(selected)
        self._update_selection_state()

    @Slot()
    def _update_selection_state(self) -> None:
        selected = sum(checkbox.isChecked() for checkbox in self._selection_boxes)
        self.export_button.setEnabled(self.document is not None and selected > 0)
        if self.document is not None:
            self.export_button.setText(f"准备当前打印（{selected} 个）")

    @Slot(int)
    def _on_label_format_changed(self, _index: int) -> None:
        self._refresh_file_statuses()

    def _selected_label_format_id(self) -> str:
        format_id = self.label_format_combo.currentData()
        if isinstance(format_id, str) and format_id:
            return format_id
        return self.exporter.DEFAULT_LABEL_FORMAT_ID

    def _refresh_file_statuses(self) -> None:
        if not self._items:
            return
        directory_text = self.output_directory_input.text().strip()
        if not directory_text:
            return
        directory = Path(directory_text)
        labels = {
            "new": "待生成",
            "reusable": "可复用",
            "update": "内容变化，需更新",
        }
        for row, item in enumerate(self._items):
            status_item = self.table.item(row, 4)
            if status_item is None:
                continue
            status = self.exporter.status(
                item,
                directory,
                label_format_id=self._selected_label_format_id(),
            )
            text = labels[status]
            status_item.setText(text)
            status_item.setToolTip(text)

    def _update_workspace_paths_label(self) -> None:
        paths = self.exporter.workspace_paths(self.workspace_root)
        self.workspace_paths_label.setText(
            f"标签库：{paths.library_directory}    当前打印：{paths.current_print_directory}"
        )
        self.workspace_paths_label.setToolTip(self.workspace_paths_label.text())

    def _set_status(self, state: str, message: str) -> None:
        colors = {
            "success": ("#ecfdf3", "#067647", "#abefc6"),
            "error": ("#fef3f2", "#b42318", "#fecdca"),
            "warning": ("#fffaeb", "#b54708", "#fedf89"),
            "neutral": ("#f2f4f7", "#344054", "#e4e7ec"),
        }
        background, color, border = colors.get(state, colors["neutral"])
        self.status_label.setProperty("feedbackState", state)
        self.status_label.setText(message)
        self.status_label.setToolTip(message)
        self.status_label.setStyleSheet(
            f"background-color: {background}; color: {color}; "
            f"border: 1px solid {border}; border-radius: 8px; padding: 9px 12px;"
        )
