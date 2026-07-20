"""Direct station/material configuration import widget."""

from pathlib import Path
from typing import Protocol

from openpyxl import Workbook
from PySide6.QtCore import Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from smt_guard.feedback import AnnouncementSink, SilentAnnouncementSink, VoicePrompt
from smt_guard.importing import ImportResult
from smt_guard.ui.components import PageHeader, content_card, prepare_table, set_feedback
from smt_guard.ui.errors import operator_error_message
from smt_guard.ui.tables import (
    UiLayoutStore,
    enable_table_layout,
    readable_item,
    set_column_widths,
    set_responsive_columns,
)


class WorkbookDropZone(QFrame):
    """Accept one local workbook while retaining a browse fallback."""

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
        self.setMinimumHeight(82)
        layout = QHBoxLayout(self)
        self.prompt_label = QLabel(prompt)
        self.path_label = QLabel("尚未选择文件")
        self.path_label.setStyleSheet("color: #667085;")
        browse_button.setProperty("actionRole", "primary")
        layout.addWidget(self.prompt_label)
        layout.addWidget(self.path_label, 1)
        layout.addWidget(browse_button)

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
            if url.isLocalFile() and Path(url.toLocalFile()).suffix.casefold() in {
                ".xlsx",
                ".xlsm",
            }:
                return url.toLocalFile()
        return ""


class ConfigurationImportWorkflow(Protocol):
    """Direct configuration import operation required by the screen."""

    def import_configuration(
        self,
        station_path: Path,
        *,
        product_code: str,
        version: str,
        station_sheet: str,
    ) -> ImportResult: ...


class ConfigurationImportWidget(QWidget):
    """Import a two-column station/material workbook without a BOM step."""

    import_completed = Signal()
    # Retained as a no-op compatibility signal for older application adapters.
    bom_imported = Signal()

    def __init__(
        self,
        workflow: ConfigurationImportWorkflow,
        parent: QWidget | None = None,
        *,
        announcer: AnnouncementSink | None = None,
        layout_store: UiLayoutStore | None = None,
    ) -> None:
        super().__init__(parent)
        self._workflow = workflow
        self._announcer = announcer or SilentAnnouncementSink()
        self._layout_store = layout_store
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(
            PageHeader(
                "导入产品配置",
                "填写产品与版本，导入仅含“站位编码、物料编码”的 Excel 表。",
            )
        )

        self.workflow_shell = content_card()
        self.workflow_shell.setMaximumWidth(1080)
        workflow_layout = QVBoxLayout(self.workflow_shell)
        workflow_layout.setSpacing(10)

        form = QFormLayout()
        self.product_code_input = QLineEdit()
        self.product_code_input.setPlaceholderText("例如：501000009")
        self.version_input = QLineEdit()
        self.version_input.setPlaceholderText("例如：0001")
        self.station_sheet_input = QLineEdit("Worksheet")
        form.addRow("产品编码", self.product_code_input)
        form.addRow("配置版本", self.version_input)
        form.addRow("工作表", self.station_sheet_input)
        workflow_layout.addLayout(form)

        self.station_path_input = QLineEdit()
        self.station_path_input.setReadOnly(True)
        self.station_browse_button = QPushButton("选择 Excel")
        self.station_drop_zone = WorkbookDropZone(
            "拖放配置表到这里",
            self.station_browse_button,
        )
        workflow_layout.addWidget(self.station_drop_zone)
        workflow_layout.addWidget(self.station_path_input)

        action_row = QHBoxLayout()
        self.template_hint = QLabel("必需列：站位编码、物料编码；旧表中的设备编码可保留")
        self.template_hint.setStyleSheet("color: #667085;")
        self.template_button = QPushButton("下载模板")
        self.station_import_button = QPushButton("导入并使用")
        self.station_import_button.setProperty("actionRole", "success")
        action_row.addWidget(self.template_hint, 1)
        action_row.addWidget(self.template_button)
        action_row.addWidget(self.station_import_button)
        workflow_layout.addLayout(action_row)

        summary = QHBoxLayout()
        self.product_label = QLabel("产品：-")
        self.version_label = QLabel("版本：-")
        self.assignment_count_label = QLabel("站位：0")
        for label in (self.product_label, self.version_label, self.assignment_count_label):
            label.setProperty("metricChip", True)
            summary.addWidget(label)
        summary.addStretch(1)
        workflow_layout.addLayout(summary)

        self.assignment_table = QTableWidget(0, 2)
        self.assignment_table.setHorizontalHeaderLabels(("站位编码", "物料编码"))
        prepare_table(self.assignment_table)
        self.assignment_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.assignment_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        set_column_widths(self.assignment_table, (220, 360))
        set_responsive_columns(self.assignment_table, stretch=(0, 1))
        enable_table_layout(
            self.assignment_table,
            "import/direct-assignments",
            self._layout_store,
        )
        workflow_layout.addWidget(self.assignment_table, 1)

        self.status_label = QLabel("请选择配置表并填写产品信息")
        self.status_label.setObjectName("feedbackLabel")
        set_feedback(self.status_label, "neutral", "请选择配置表并填写产品信息")
        workflow_layout.addWidget(self.status_label)

        centered = QHBoxLayout()
        centered.addStretch(1)
        centered.addWidget(self.workflow_shell, 20, Qt.AlignmentFlag.AlignTop)
        centered.addStretch(1)
        layout.addLayout(centered, 1)

    def _connect_signals(self) -> None:
        self.station_browse_button.clicked.connect(self._select_station_table)
        self.template_button.clicked.connect(self._download_template)
        self.station_import_button.clicked.connect(self._import_configuration)
        self.station_drop_zone.path_dropped.connect(self.station_path_input.setText)
        self.station_path_input.textChanged.connect(self.station_drop_zone.show_path)

    @Slot()
    def _select_station_table(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "选择产品配置表",
            self.station_path_input.text().strip(),
            "Excel 工作簿 (*.xlsx *.xlsm)",
        )
        if selected:
            self.station_path_input.setText(selected)

    @Slot()
    def _download_template(self) -> None:
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "保存产品配置模板",
            "SMTGuard-产品配置模板.xlsx",
            "Excel 工作簿 (*.xlsx)",
        )
        if not selected:
            return
        path = Path(selected)
        if path.suffix.lower() != ".xlsx":
            path = path.with_suffix(".xlsx")
        workbook = Workbook()
        try:
            sheet = workbook.active
            if sheet is None:
                raise OSError("无法创建工作表")
            sheet.title = "Worksheet"
            sheet.append(["站位编码", "物料编码"])
            sheet.append(["F-01", "示例物料编码"])
            sheet.freeze_panes = "A2"
            sheet.column_dimensions["A"].width = 22
            sheet.column_dimensions["B"].width = 28
            workbook.save(path)
        except OSError as error:
            self._show_error(f"模板保存失败：{error}")
            return
        finally:
            workbook.close()
        self._show_success(f"模板已保存：{path}")

    @Slot()
    def _import_configuration(self) -> None:
        try:
            result = self._workflow.import_configuration(
                Path(self._required(self.station_path_input.text(), "配置表文件")),
                product_code=self._required(self.product_code_input.text(), "产品编码"),
                version=self._required(self.version_input.text(), "配置版本"),
                station_sheet=self._required(self.station_sheet_input.text(), "工作表"),
            )
        except (OSError, ValueError) as error:
            self._show_error(operator_error_message(error))
            self._announcer.announce(VoicePrompt.IMPORT_FAILED)
            return

        self._preview(result)
        self._show_success(
            f"导入成功：产品 {result.configuration.product_code}/{result.configuration.version} "
            f"已启用，可直接开始扫码，共 {len(result.configuration.assignments)} 个站位"
        )
        self._announcer.announce(VoicePrompt.CONFIGURATION_IMPORTED)
        self.import_completed.emit()

    def _preview(self, result: ImportResult) -> None:
        configuration = result.configuration
        self.product_label.setText(f"产品：{configuration.product_code}")
        self.version_label.setText(f"版本：{configuration.version}")
        assignments = sorted(configuration.assignments.items())
        self.assignment_count_label.setText(f"站位：{len(assignments)}")
        self.assignment_table.setRowCount(len(assignments))
        for row, ((_, station), material) in enumerate(assignments):
            self.assignment_table.setItem(row, 0, readable_item(station))
            self.assignment_table.setItem(row, 1, readable_item(material))

    def _show_success(self, message: str) -> None:
        set_feedback(self.status_label, "success", message)

    def _show_error(self, message: str) -> None:
        set_feedback(self.status_label, "error", message)

    @staticmethod
    def _required(value: str, label: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{label}不能为空")
        return normalized
