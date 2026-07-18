"""Verification record query and CSV export widget."""

from pathlib import Path
from typing import Protocol

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from smt_guard.feedback import AnnouncementSink, SilentAnnouncementSink, VoicePrompt
from smt_guard.records import Attempt
from smt_guard.ui.components import (
    EmptyState,
    PageHeader,
    content_card,
    prepare_table,
    section_heading,
    set_feedback,
)
from smt_guard.ui.formatting import display_datetime
from smt_guard.ui.tables import (
    readable_item,
    set_column_widths,
    set_responsive_columns,
)


class AttemptReader(Protocol):
    """Read attempts for one run."""

    def list_for_run(self, run_id: str) -> list[Attempt]:
        """Return attempts in identifier order."""
        ...


class RunExporter(Protocol):
    """Export one run to a selected path."""

    def export_run(self, run_id: str, path: Path) -> None:
        """Write one run's records."""
        ...


class RecordQueryWidget(QWidget):
    """Query exact run identifiers and export their attempt history."""

    HEADERS = (
        "编号",
        "时间",
        "运行编号",
        "产品",
        "版本",
        "设备",
        "站位",
        "要求物料",
        "扫码物料",
        "结果",
        "重复",
    )

    def __init__(
        self,
        repository: AttemptReader,
        exporter: RunExporter,
        parent: QWidget | None = None,
        *,
        announcer: AnnouncementSink | None = None,
    ) -> None:
        super().__init__(parent)
        self._repository = repository
        self._exporter = exporter
        self._announcer = announcer or SilentAnnouncementSink()
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(
            PageHeader(
                "扫码记录查询",
                "输入生产运行编号，集中查看该运行的 OK、NG 与重复扫码记录。",
            )
        )

        query_card = content_card(object_name="filterCard")
        query_layout = QVBoxLayout(query_card)
        query_layout.addWidget(section_heading("查找运行", "运行编号可从“生产运行”页直接带入"))
        query_row = QHBoxLayout()
        self.run_id_input = QLineEdit()
        self.run_id_input.setPlaceholderText("输入运行编号")
        self.run_id_input.setClearButtonEnabled(True)
        self.run_id_input.setMaximumWidth(720)
        self.query_button = QPushButton("查询")
        self.query_button.setProperty("actionRole", "primary")
        query_row.addWidget(self.run_id_input, 1)
        query_row.addWidget(self.query_button)
        query_row.addStretch(1)
        query_layout.addLayout(query_row)
        layout.addWidget(query_card)

        result_card = content_card()
        result_layout = QVBoxLayout(result_card)
        result_header = QHBoxLayout()
        self.result_title = QLabel("等待查询")
        self.result_title.setObjectName("sectionTitle")
        self.total_chip = QLabel("0 条")
        self.ng_chip = QLabel("NG 0")
        self.repeat_chip = QLabel("重复 0")
        for chip in (self.total_chip, self.ng_chip, self.repeat_chip):
            chip.setProperty("metricChip", True)
        self.ng_chip.setProperty("metricTone", "danger")
        self.repeat_chip.setProperty("metricTone", "primary")
        result_header.addWidget(self.result_title)
        result_header.addStretch(1)
        result_header.addWidget(self.total_chip)
        result_header.addWidget(self.ng_chip)
        result_header.addWidget(self.repeat_chip)
        result_layout.addLayout(result_header)

        export_row = QHBoxLayout()
        self.export_path_input = QLineEdit()
        self.export_path_input.setPlaceholderText("选择 CSV 导出路径")
        self.export_browse_button = QPushButton("选择路径")
        self.export_button = QPushButton("导出当前运行")
        self.export_button.setProperty("actionRole", "primary")
        export_row.addWidget(self.export_path_input, 1)
        export_row.addWidget(self.export_browse_button)
        export_row.addWidget(self.export_button)
        result_layout.addLayout(export_row)

        self.record_stack = QStackedWidget()
        self.empty_state = EmptyState(
            "输入运行编号开始查询",
            "查询后只显示当前运行最重要的扫码字段，完整信息仍保留在单元格提示中。",
        )
        self.record_stack.addWidget(self.empty_state)
        self.record_table = QTableWidget(0, len(self.HEADERS))
        self.record_table.setHorizontalHeaderLabels(self.HEADERS)
        prepare_table(self.record_table)
        self.record_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.record_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        set_column_widths(
            self.record_table,
            (70, 145, 220, 120, 160, 100, 90, 150, 150, 65, 60),
        )
        for hidden_column in (0, 2, 3, 4):
            self.record_table.setColumnHidden(hidden_column, True)
        set_responsive_columns(
            self.record_table,
            stretch=(1, 5, 6, 7, 8),
            compact=(9, 10),
        )
        self.record_stack.addWidget(self.record_table)
        result_layout.addWidget(self.record_stack, 1)
        layout.addWidget(result_card, 1)

        self.status_label = QLabel("请输入运行编号")
        set_feedback(self.status_label, "neutral", "请输入运行编号")
        layout.addWidget(self.status_label)

    def _connect_signals(self) -> None:
        self.query_button.clicked.connect(self._query)
        self.run_id_input.returnPressed.connect(self._query)
        self.export_browse_button.clicked.connect(self._select_export_path)
        self.export_button.clicked.connect(self._export)

    @Slot()
    def _query(self) -> None:
        try:
            run_id = self._required(self.run_id_input.text(), "运行编号")
        except ValueError as error:
            self._show_error(str(error))
            return
        records = self._repository.list_for_run(run_id)
        self._render_records(records)
        if records:
            self._show_success(f"找到 {len(records)} 条记录")
        else:
            self._show_neutral(f"未找到运行 {run_id} 的记录")

    @Slot()
    def _select_export_path(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出扫码记录",
            self.export_path_input.text().strip(),
            "CSV 文件 (*.csv)",
        )
        if path:
            self.export_path_input.setText(path)

    @Slot()
    def _export(self) -> None:
        try:
            run_id = self._required(self.run_id_input.text(), "运行编号")
            path = Path(self._required(self.export_path_input.text(), "导出路径"))
            self._exporter.export_run(run_id, path)
        except (OSError, ValueError) as error:
            self._show_error(str(error))
            self._announcer.announce(VoicePrompt.EXPORT_FAILED)
            return
        self._show_success(f"已导出运行 {run_id} 到 {path}")
        self._announcer.announce(VoicePrompt.RECORDS_EXPORTED)

    def _render_records(self, records: list[Attempt]) -> None:
        self.record_table.setRowCount(len(records))
        for row, attempt in enumerate(records):
            values = (
                str(attempt.id or ""),
                display_datetime(attempt.timestamp),
                attempt.run_id,
                attempt.product_code,
                attempt.product_version,
                attempt.device_code,
                attempt.station_code,
                attempt.expected_material,
                attempt.scanned_material,
                attempt.result.value,
                "是" if attempt.repeated else "否",
            )
            for column, value in enumerate(values):
                self.record_table.setItem(row, column, readable_item(value))
        ng_count = sum(attempt.result.value == "NG" for attempt in records)
        repeat_count = sum(attempt.repeated for attempt in records)
        self.total_chip.setText(f"{len(records)} 条")
        self.ng_chip.setText(f"NG {ng_count}")
        self.repeat_chip.setText(f"重复 {repeat_count}")
        if records:
            first = records[0]
            self.result_title.setText(
                f"{first.run_id} · {first.product_code}/{first.product_version}"
            )
            self.record_stack.setCurrentWidget(self.record_table)
        else:
            run_id = self.run_id_input.text().strip()
            self.result_title.setText(run_id or "没有查询结果")
            self.empty_state.set_message(
                "没有扫码记录",
                f"运行 {run_id} 尚无扫码记录，请确认运行编号或前往生产运行页查看状态。",
            )
            self.record_stack.setCurrentWidget(self.empty_state)

    def _show_success(self, message: str) -> None:
        set_feedback(self.status_label, "success", message)

    def _show_neutral(self, message: str) -> None:
        set_feedback(self.status_label, "neutral", message)

    def _show_error(self, message: str) -> None:
        set_feedback(self.status_label, "error", message)

    @staticmethod
    def _required(value: str, label: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{label}不能为空")
        return normalized
