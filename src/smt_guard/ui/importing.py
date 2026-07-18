"""BOM and station-table import widget."""

from pathlib import Path
from typing import Protocol

from PySide6.QtCore import Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from smt_guard.bom import BomDocument
from smt_guard.feedback import AnnouncementSink, SilentAnnouncementSink, VoicePrompt
from smt_guard.importing import ImportResult
from smt_guard.ui.components import PageHeader, prepare_table, set_feedback
from smt_guard.ui.errors import operator_error_message
from smt_guard.ui.tables import (
    readable_item,
    set_column_widths,
    set_responsive_columns,
)


class WorkbookDropZone(QFrame):
    """Accept one local workbook while retaining an explicit browse fallback."""

    path_dropped = Signal(str)

    def __init__(
        self,
        prompt: str,
        browse_button: QPushButton,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(105)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.prompt_label = QLabel(prompt)
        self.prompt_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.path_label = QLabel("尚未选择文件")
        self.path_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.path_label.setStyleSheet("color: #667085;")
        browse_button.setProperty("actionRole", "primary")
        layout.addWidget(self.prompt_label)
        layout.addWidget(browse_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.path_label)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._workbook_path(event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        path = self._workbook_path(event.mimeData().urls())
        if path:
            self.path_dropped.emit(path)
            event.acceptProposedAction()

    @Slot(str)
    def show_path(self, path: str) -> None:
        self.path_label.setText(Path(path).name if path else "尚未选择文件")

    @staticmethod
    def _workbook_path(urls: list[QUrl]) -> str:
        for url in urls:
            if not url.isLocalFile():
                continue
            path = url.toLocalFile()
            if Path(path).suffix.casefold() in {".xlsx", ".xlsm"}:
                return path
        return ""


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
        *,
        announcer: AnnouncementSink | None = None,
    ) -> None:
        super().__init__(parent)
        self._workflow = workflow
        self._announcer = announcer or SilentAnnouncementSink()
        self._current_step = 1
        self._bom_document: BomDocument | None = None
        self._build_ui()
        self._connect_signals()
        self._set_step(1)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(
            PageHeader(
                "导入配置",
                "按顺序导入 BOM 与站位表，系统校验通过后才会启用产品配置。",
            )
        )
        self.workflow_shell = QWidget()
        self.workflow_shell.setMaximumWidth(1280)
        workflow_layout = QVBoxLayout(self.workflow_shell)
        workflow_layout.setContentsMargins(0, 0, 0, 0)
        workflow_layout.setSpacing(10)
        self.step_indicator = QLabel()
        self.step_indicator.setObjectName("stepIndicator")
        workflow_layout.addWidget(self.step_indicator)

        self.bom_step = QGroupBox("第一步：导入 BOM")
        bom_layout = QVBoxLayout(self.bom_step)
        bom_layout.addWidget(QLabel("选择 BOM 工作簿。导入成功后会自动进入站位表步骤。"))
        form = QFormLayout()
        self.bom_path_input = QLineEdit()
        self.bom_path_input.setReadOnly(True)
        self.bom_browse_button = QPushButton("选择文件")
        self.bom_drop_zone = WorkbookDropZone(
            "拖放 BOM 文件到这里",
            self.bom_browse_button,
        )
        bom_layout.addWidget(self.bom_drop_zone)
        self.bom_import_button = QPushButton("导入 BOM 并继续")
        self.bom_import_button.setProperty("actionRole", "primary")
        form.addRow("已选文件", self.bom_path_input)
        self.bom_version_input = QLineEdit()
        self.bom_version_input.setPlaceholderText("可选；同一 BOM 修改后请填写新版本")
        form.addRow("BOM 新版本", self.bom_version_input)
        bom_layout.addLayout(form)
        bom_actions = QHBoxLayout()
        bom_actions.addStretch(1)
        bom_actions.addWidget(self.bom_import_button)
        bom_layout.addLayout(bom_actions)
        workflow_layout.addWidget(self.bom_step)

        self.station_step = QGroupBox("第二步：导入站位表")
        station_layout = QVBoxLayout(self.station_step)
        self.bom_summary_label = QLabel("BOM：-")
        self.bom_summary_label.setStyleSheet("color: #067647; font-weight: 600;")
        station_layout.addWidget(self.bom_summary_label)
        station_form = QFormLayout()
        self.station_path_input = QLineEdit()
        self.station_path_input.setReadOnly(True)
        self.station_browse_button = QPushButton("选择文件")
        self.station_drop_zone = WorkbookDropZone(
            "拖放站位表文件到这里",
            self.station_browse_button,
        )
        station_layout.addWidget(self.station_drop_zone)
        station_form.addRow("已选文件", self.station_path_input)

        self.station_sheet_input = QLineEdit("Worksheet")
        self.version_input = QLineEdit()
        station_form.addRow("站位工作表", self.station_sheet_input)
        station_form.addRow("产品版本", self.version_input)
        station_layout.addLayout(station_form)
        station_actions = QHBoxLayout()
        self.back_to_bom_button = QPushButton("返回上一步")
        self.review_button = QPushButton("下一步：校验")
        self.review_button.setProperty("actionRole", "primary")
        station_actions.addWidget(self.back_to_bom_button)
        station_actions.addStretch(1)
        station_actions.addWidget(self.review_button)
        station_layout.addLayout(station_actions)
        workflow_layout.addWidget(self.station_step)

        self.validation_step = QGroupBox("第三步：校验并启用")
        validation_layout = QVBoxLayout(self.validation_step)
        self.validation_label = QLabel("确认摘要后执行校验。校验通过会立即启用产品配置。")
        self.validation_label.setWordWrap(True)
        validation_layout.addWidget(self.validation_label)
        summary = QHBoxLayout()
        self.product_label = QLabel("产品：-")
        self.bom_number_label = QLabel("BOM：-")
        self.material_count_label = QLabel("BOM 组件：0")
        self.assignment_count_label = QLabel("站位分配：0")
        for label in (
            self.product_label,
            self.bom_number_label,
            self.material_count_label,
            self.assignment_count_label,
        ):
            label.setProperty("metricChip", True)
            summary.addWidget(label)
        summary.addStretch(1)
        validation_layout.addLayout(summary)

        self.assignment_table = QTableWidget(0, 3)
        self.assignment_table.setHorizontalHeaderLabels(("设备编码", "站位编码", "物料编码"))
        prepare_table(self.assignment_table)
        self.assignment_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.assignment_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        set_column_widths(self.assignment_table, (150, 150, 240))
        set_responsive_columns(self.assignment_table, stretch=(0, 1, 2))
        validation_layout.addWidget(self.assignment_table, 1)

        validation_actions = QHBoxLayout()
        self.back_to_station_button = QPushButton("返回修改")
        self.station_import_button = QPushButton("校验并启用")
        self.station_import_button.setProperty("actionRole", "success")
        validation_actions.addWidget(self.back_to_station_button)
        validation_actions.addStretch(1)
        validation_actions.addWidget(self.station_import_button)
        validation_layout.addLayout(validation_actions)
        workflow_layout.addWidget(self.validation_step, 1)

        self.status_label = QLabel("请先导入 BOM，再导入站位表")
        self.status_label.setObjectName("feedbackLabel")
        workflow_layout.addWidget(self.status_label)
        centered = QHBoxLayout()
        centered.addStretch(1)
        centered.addWidget(self.workflow_shell, 24, Qt.AlignmentFlag.AlignTop)
        centered.addStretch(1)
        layout.addLayout(centered, 1)

    def _connect_signals(self) -> None:
        self.bom_browse_button.clicked.connect(self._select_bom)
        self.station_browse_button.clicked.connect(self._select_station_table)
        self.bom_import_button.clicked.connect(self._import_bom)
        self.station_import_button.clicked.connect(self._import_station_table)
        self.review_button.clicked.connect(self._review_station_table)
        self.back_to_bom_button.clicked.connect(lambda: self._set_step(1))
        self.back_to_station_button.clicked.connect(lambda: self._set_step(2))
        self.bom_drop_zone.path_dropped.connect(self.bom_path_input.setText)
        self.station_drop_zone.path_dropped.connect(self.station_path_input.setText)
        self.bom_path_input.textChanged.connect(self.bom_drop_zone.show_path)
        self.station_path_input.textChanged.connect(self.station_drop_zone.show_path)

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
            self._show_error(operator_error_message(error))
            self._announcer.announce(VoicePrompt.IMPORT_FAILED)
            return

        self._preview_bom(document)
        self._bom_document = document
        self._show_success(f"BOM 产品 {document.product.material_code} 导入成功")
        self._announcer.announce(VoicePrompt.BOM_IMPORTED)
        self.bom_imported.emit()
        self._set_step(2)

    @Slot()
    def _review_station_table(self) -> None:
        try:
            self._required(self.station_path_input.text(), "站位表文件")
            self._required(self.station_sheet_input.text(), "站位工作表")
            self._required(self.version_input.text(), "产品版本")
        except ValueError as error:
            self._show_error(str(error))
            return
        self.station_import_button.setEnabled(True)
        self.validation_label.setStyleSheet("color: #344054;")
        self.validation_label.setText(
            f"将校验 {Path(self.station_path_input.text().strip()).name}，"
            f"通过后启用产品版本 {self.version_input.text().strip()}。"
        )
        self._set_step(3)

    @Slot()
    def _import_station_table(self) -> None:
        try:
            station_path = Path(self._required(self.station_path_input.text(), "站位表文件"))
            sheet = self._required(self.station_sheet_input.text(), "站位工作表")
            version = self._required(self.version_input.text(), "产品版本")
            result = self._workflow.import_station_table(
                station_path,
                version=version,
                station_sheet=sheet,
            )
        except (OSError, ValueError) as error:
            self._show_error(operator_error_message(error))
            self._announcer.announce(VoicePrompt.IMPORT_FAILED)
            return

        self._preview(result)
        self.station_import_button.setEnabled(False)
        self.validation_label.setStyleSheet("color: #067647; font-weight: 600;")
        self.validation_label.setText("校验通过，产品配置已启用，可以前往扫码作业。")
        self._show_success(
            f"产品 {result.configuration.product_code}/{result.configuration.version} 导入成功"
        )
        self._announcer.announce(VoicePrompt.CONFIGURATION_IMPORTED)
        self.import_completed.emit()

    def _preview_bom(self, document: BomDocument) -> None:
        product = document.product
        self.product_label.setText(f"产品：{product.material_code} {product.name}")
        self.bom_number_label.setText(f"BOM：{product.bom_number}")
        self.material_count_label.setText(f"BOM 组件：{len(document.materials)}")
        self.assignment_count_label.setText("站位分配：0")
        self.assignment_table.setRowCount(0)
        self.bom_summary_label.setText(
            f"已导入 BOM：{product.bom_number} · 产品 {product.material_code} · "
            f"{len(document.materials)} 个物料"
        )

    def _preview(self, result: ImportResult) -> None:
        product = result.document.product
        self.product_label.setText(f"产品：{product.material_code} {product.name}")
        self.material_count_label.setText(f"BOM 组件：{len(result.document.materials)}")
        assignments = sorted(result.configuration.assignments.items())
        self.assignment_count_label.setText(f"站位分配：{len(assignments)}")
        self.assignment_table.setRowCount(len(assignments))
        for row, ((device, station), material) in enumerate(assignments):
            self.assignment_table.setItem(row, 0, readable_item(device))
            self.assignment_table.setItem(row, 1, readable_item(station))
            self.assignment_table.setItem(row, 2, readable_item(material))

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
        set_feedback(self.status_label, "success", message)

    def _show_error(self, message: str) -> None:
        set_feedback(self.status_label, "error", message)

    def _set_step(self, step: int) -> None:
        self._current_step = step
        self.bom_step.setVisible(step == 1)
        self.station_step.setVisible(step == 2)
        self.validation_step.setVisible(step == 3)
        labels = {
            1: "● ① 导入 BOM   →   ② 导入站位表   →   ③ 校验并启用",
            2: "✓ ① 导入 BOM   →   ● ② 导入站位表   →   ③ 校验并启用",
            3: "✓ ① 导入 BOM   →   ✓ ② 导入站位表   →   ● ③ 校验并启用",
        }
        self.step_indicator.setText(labels[step])
        self.step_indicator.setStyleSheet(
            "font-size: 17px; font-weight: 700; padding: 12px 16px; "
            "color: #175cd3; background-color: #eff8ff; "
            "border: 1px solid #b2ddff; border-radius: 10px;"
        )

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
