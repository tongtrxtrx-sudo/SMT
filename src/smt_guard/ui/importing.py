"""BOM and station-table import widget."""

from pathlib import Path
from typing import Protocol

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from smt_guard.bom import BomDocument
from smt_guard.importing import ImportResult


class ConfigurationImportWorkflow(Protocol):
    """Import operation required by the configuration screen."""

    def import_bom(self, bom_path: Path, *, version: str | None = None) -> BomDocument:
        """Load and validate one BOM."""
        ...

    def import_station_table(
        self,
        station_path: Path,
        *,
        version: str,
        station_sheet: str,
    ) -> ImportResult:
        """Import stations against the previously loaded BOM."""
        ...


class ConfigurationImportWidget(QWidget):
    """Collect workbook inputs and preview imported station assignments."""

    import_completed = Signal()
    bom_imported = Signal()

    def __init__(
        self,
        workflow: ConfigurationImportWorkflow,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._workflow = workflow
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("BOM 与站位表导入")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        form = QFormLayout()
        self.bom_path_input = QLineEdit()
        self.bom_browse_button = QPushButton("选择文件")
        self.bom_import_button = QPushButton("导入 BOM")
        form.addRow(
            "BOM 文件",
            self._path_row(
                self.bom_path_input,
                self.bom_browse_button,
                self.bom_import_button,
            ),
        )

        self.station_path_input = QLineEdit()
        self.station_browse_button = QPushButton("选择文件")
        self.station_import_button = QPushButton("导入站位表")
        form.addRow(
            "站位表文件",
            self._path_row(
                self.station_path_input,
                self.station_browse_button,
                self.station_import_button,
            ),
        )

        self.station_sheet_input = QLineEdit("Worksheet")
        self.version_input = QLineEdit()
        self.bom_version_input = QLineEdit()
        self.bom_version_input.setPlaceholderText("可选；同一 BOM 修改后请填写新版本")
        form.addRow("BOM 新版本", self.bom_version_input)
        form.addRow("站位工作表", self.station_sheet_input)
        form.addRow("产品版本", self.version_input)
        layout.addLayout(form)

        summary = QHBoxLayout()
        self.product_label = QLabel("产品：-")
        self.material_count_label = QLabel("BOM 组件：0")
        self.assignment_count_label = QLabel("站位分配：0")
        summary.addWidget(self.product_label)
        summary.addWidget(self.material_count_label)
        summary.addWidget(self.assignment_count_label)
        summary.addStretch(1)
        layout.addLayout(summary)

        self.assignment_table = QTableWidget(0, 3)
        self.assignment_table.setHorizontalHeaderLabels(("设备编码", "站位编码", "物料编码"))
        self.assignment_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.assignment_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.assignment_table.verticalHeader().setVisible(False)
        layout.addWidget(self.assignment_table, 1)

        self.status_label = QLabel("请先导入 BOM，再导入站位表")
        self.status_label.setObjectName("feedbackLabel")
        layout.addWidget(self.status_label)

    def _connect_signals(self) -> None:
        self.bom_browse_button.clicked.connect(self._select_bom)
        self.station_browse_button.clicked.connect(self._select_station_table)
        self.bom_import_button.clicked.connect(self._import_bom)
        self.station_import_button.clicked.connect(self._import_station_table)

    @Slot()
    def _select_bom(self) -> None:
        self._select_xlsx(self.bom_path_input, "选择 BOM 文件")

    @Slot()
    def _select_station_table(self) -> None:
        self._select_xlsx(self.station_path_input, "选择站位表文件")

    @Slot()
    def _import_bom(self) -> None:
        try:
            bom_path = Path(self._required(self.bom_path_input.text(), "BOM 文件"))
            bom_version = self.bom_version_input.text().strip()
            if bom_version:
                document = self._workflow.import_bom(bom_path, version=bom_version)
            else:
                document = self._workflow.import_bom(bom_path)
        except (OSError, ValueError) as error:
            self._show_error(str(error))
            return

        self._preview_bom(document)
        self._show_success(f"BOM 产品 {document.product.material_code} 导入成功")
        self.bom_imported.emit()

    @Slot()
    def _import_station_table(self) -> None:
        try:
            station_path = Path(
                self._required(self.station_path_input.text(), "站位表文件")
            )
            sheet = self._required(self.station_sheet_input.text(), "站位工作表")
            version = self._required(self.version_input.text(), "产品版本")
            result = self._workflow.import_station_table(
                station_path,
                version=version,
                station_sheet=sheet,
            )
        except (OSError, ValueError) as error:
            self._show_error(str(error))
            return

        self._preview(result)
        self._show_success(
            f"产品 {result.configuration.product_code}/{result.configuration.version} 导入成功"
        )
        self.import_completed.emit()

    def _preview_bom(self, document: BomDocument) -> None:
        product = document.product
        self.product_label.setText(f"产品：{product.material_code} {product.name}")
        self.material_count_label.setText(f"BOM 组件：{len(document.materials)}")
        self.assignment_count_label.setText("站位分配：0")
        self.assignment_table.setRowCount(0)

    def _preview(self, result: ImportResult) -> None:
        product = result.document.product
        self.product_label.setText(f"产品：{product.material_code} {product.name}")
        self.material_count_label.setText(f"BOM 组件：{len(result.document.materials)}")
        assignments = sorted(result.configuration.assignments.items())
        self.assignment_count_label.setText(f"站位分配：{len(assignments)}")
        self.assignment_table.setRowCount(len(assignments))
        for row, ((device, station), material) in enumerate(assignments):
            self.assignment_table.setItem(row, 0, QTableWidgetItem(device))
            self.assignment_table.setItem(row, 1, QTableWidgetItem(station))
            self.assignment_table.setItem(row, 2, QTableWidgetItem(material))

    def _select_xlsx(self, target: QLineEdit, caption: str) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            caption,
            target.text().strip(),
            "Excel 工作簿 (*.xlsx)",
        )
        if selected:
            target.setText(selected)

    def _show_success(self, message: str) -> None:
        self.status_label.setProperty("feedbackState", "success")
        self.status_label.setStyleSheet("color: #18794e;")
        self.status_label.setText(message)

    def _show_error(self, message: str) -> None:
        self.status_label.setProperty("feedbackState", "error")
        self.status_label.setStyleSheet("color: #b42318;")
        self.status_label.setText(message)

    @staticmethod
    def _required(value: str, label: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{label}不能为空")
        return normalized

    @staticmethod
    def _path_row(path_input: QLineEdit, *buttons: QPushButton) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(path_input, 1)
        for button in buttons:
            layout.addWidget(button)
        return container
