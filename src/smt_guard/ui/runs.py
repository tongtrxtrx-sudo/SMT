"""Production run query and recovery page."""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from smt_guard.feedback import AnnouncementSink, SilentAnnouncementSink, VoicePrompt
from smt_guard.records import Attempt
from smt_guard.run import ProductionRun, RunStationState, RunStatus
from smt_guard.ui.components import (
    PageHeader,
    content_card,
    prepare_table,
    section_heading,
    set_feedback,
)
from smt_guard.ui.date_range import DateRangeFilter
from smt_guard.ui.formatting import display_datetime
from smt_guard.ui.tables import (
    readable_item,
    set_column_widths,
    set_responsive_columns,
)


class ProductionRunReader(Protocol):
    def search_runs(
        self,
        query: str = "",
        *,
        operator: str = "",
        status: RunStatus | None = None,
        started_from: datetime | None = None,
        started_to: datetime | None = None,
    ) -> list[ProductionRun]: ...

    def list_station_states(self, run_id: str) -> list[RunStationState]: ...

    def list_for_run(self, run_id: str) -> list[Attempt]: ...


class RunExporter(Protocol):
    def export_run(self, run_id: str, path: Path) -> None: ...


class ProductionRunManagementWidget(QWidget):
    """Search run snapshots and request scanner start or recovery."""

    start_requested = Signal()
    resume_requested = Signal(str)
    interrupt_requested = Signal(str, str)

    def __init__(
        self,
        repository: ProductionRunReader,
        parent: QWidget | None = None,
        *,
        exporter: RunExporter | None = None,
        announcer: AnnouncementSink | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        super().__init__(parent)
        self._repository = repository
        self._exporter = exporter
        self._announcer = announcer or SilentAnnouncementSink()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._runs: list[ProductionRun] = []
        self._wide_layout: bool | None = None
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(
            PageHeader(
                "生产运行",
                "统一查看每次扫码作业的进度、NG、站位与扫码记录，并处理恢复、中断或导出。",
            )
        )
        filter_card = content_card(object_name="filterCard")
        filter_layout = QVBoxLayout(filter_card)
        filter_layout.addWidget(section_heading("筛选运行", "默认查询最近 7 天"))
        filters = QHBoxLayout()
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("运行号、产品或版本")
        self.operator_input = QLineEdit()
        self.operator_input.setPlaceholderText("操作员")
        self.status_combo = QComboBox()
        self.status_combo.addItems(("全部状态", "运行中", "已完成", "已中断"))
        self.query_button = QPushButton("查询")
        self.query_button.setProperty("actionRole", "primary")
        self.query_input.setMaximumWidth(560)
        self.operator_input.setMaximumWidth(320)
        filters.addWidget(self.query_input, 2)
        filters.addWidget(self.operator_input, 1)
        filters.addWidget(self.status_combo)
        filters.addStretch(1)
        filters.addWidget(self.query_button)
        filter_layout.addLayout(filters)
        self.date_range = DateRangeFilter(clock=self._clock, default_days=7)
        self.started_from_input = self.date_range.started_from_input
        self.started_to_input = self.date_range.started_to_input
        filter_layout.addWidget(self.date_range)
        layout.addWidget(filter_card)

        self.start_button = QPushButton("转到扫码开始")
        self.start_button.setProperty("actionRole", "primary")
        self.resume_button = QPushButton("恢复所选运行")
        self.resume_button.setProperty("actionRole", "success")
        self.view_records_button = QPushButton("查看扫码记录")
        self.view_records_button.setProperty("actionRole", "primary")
        self.export_button = QPushButton("导出 CSV")
        self.interruption_reason_input = QLineEdit("人工中断")
        self.interrupt_button = QPushButton("中断运行")
        self.interrupt_button.setProperty("actionRole", "danger")
        self.refresh_button = QPushButton("刷新")

        splitter = QSplitter()
        self.splitter = splitter
        run_list_card = content_card()
        run_list_layout = QVBoxLayout(run_list_card)
        run_list_heading = QHBoxLayout()
        run_list_heading.addWidget(section_heading("运行列表", "选择后查看右侧详情"), 1)
        self.run_count_chip = QLabel("0 个")
        self.run_count_chip.setProperty("metricChip", True)
        self.run_count_chip.setProperty("metricTone", "primary")
        run_list_heading.addWidget(self.run_count_chip)
        run_list_layout.addLayout(run_list_heading)
        self.run_table = QTableWidget(0, 6)
        self.run_table.setHorizontalHeaderLabels(
            ("运行号", "产品 / 版本", "操作员", "状态", "进度", "开始时间")
        )
        prepare_table(self.run_table)
        self.run_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.run_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.run_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.run_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        set_column_widths(
            self.run_table,
            (160, 140, 75, 65, 55, 115),
        )
        set_responsive_columns(
            self.run_table,
            stretch=(1,),
            compact=(2, 3, 4),
        )
        run_list_layout.addWidget(self.run_table, 1)
        splitter.addWidget(run_list_card)
        right = QFrame()
        right.setObjectName("runSummaryCard")
        right_layout = QVBoxLayout(right)
        self.run_summary_title = QLabel("请选择生产运行")
        self.run_summary_title.setObjectName("productSummary")
        right_layout.addWidget(self.run_summary_title)
        chips = QHBoxLayout()
        self.run_status_chip = QLabel("状态 -")
        self.run_progress_chip = QLabel("0 / 0")
        self.run_ng_chip = QLabel("NG 0")
        for chip in (
            self.run_status_chip,
            self.run_progress_chip,
            self.run_ng_chip,
        ):
            chip.setProperty("summaryChip", True)
            chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chips.addWidget(chip)
        self.run_status_chip.setStyleSheet("background: #f2f4f7; color: #475467;")
        self.run_progress_chip.setStyleSheet("background: #eff8ff; color: #175cd3;")
        self.run_ng_chip.setStyleSheet("background: #fef3f2; color: #d92d20;")
        right_layout.addLayout(chips)
        self.snapshot_label = QLabel("请选择生产运行")
        self.snapshot_label.setWordWrap(True)
        right_layout.addWidget(self.snapshot_label)
        self.detail_tabs = QTabWidget()
        self.station_table = QTableWidget(0, 5)
        self.station_table.setHorizontalHeaderLabels(
            ("设备", "站位", "要求物料", "状态", "完成时间")
        )
        prepare_table(self.station_table)
        self.station_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.station_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        set_column_widths(self.station_table, (65, 50, 110, 55, 95))
        set_responsive_columns(
            self.station_table,
            stretch=(0, 1, 2, 4),
            compact=(3,),
        )
        self.detail_tabs.addTab(self.station_table, "站位进度")
        attempts_page = QWidget()
        attempts_layout = QVBoxLayout(attempts_page)
        attempts_layout.setContentsMargins(0, 0, 0, 0)
        self.attempt_summary_label = QLabel("扫码记录：0 条")
        attempts_layout.addWidget(self.attempt_summary_label)
        self.attempt_table = QTableWidget(0, 7)
        self.attempt_table.setHorizontalHeaderLabels(
            ("时间", "设备", "站位", "要求物料", "扫码物料", "结果", "重复")
        )
        prepare_table(self.attempt_table)
        self.attempt_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.attempt_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        set_column_widths(self.attempt_table, (150, 100, 100, 170, 170, 70, 70))
        set_responsive_columns(
            self.attempt_table,
            stretch=(0, 1, 2, 3, 4),
            compact=(5, 6),
        )
        attempts_layout.addWidget(self.attempt_table, 1)
        self.detail_tabs.addTab(attempts_page, "扫码记录")
        right_layout.addWidget(self.detail_tabs, 1)
        reason_row = QHBoxLayout()
        reason_row.addWidget(QLabel("中断原因"))
        reason_row.addWidget(self.interruption_reason_input, 1)
        right_layout.addLayout(reason_row)
        detail_actions = QHBoxLayout()
        detail_actions.addWidget(self.view_records_button)
        detail_actions.addWidget(self.export_button)
        detail_actions.addWidget(self.interrupt_button)
        right_layout.addLayout(detail_actions)
        splitter.addWidget(right)
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)
        splitter.setSizes((720, 1080))
        layout.addWidget(splitter, 1)

        actions = QHBoxLayout()
        actions.addWidget(self.start_button)
        actions.addWidget(self.resume_button)
        actions.addWidget(self.refresh_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        self.status_label = QLabel("就绪")
        set_feedback(self.status_label, "neutral", "就绪")
        layout.addWidget(self.status_label)

        self.query_button.clicked.connect(self.refresh)
        self.refresh_button.clicked.connect(self.refresh)
        self.query_input.returnPressed.connect(self.refresh)
        self.date_range.range_selected.connect(self.refresh)
        self.run_table.itemSelectionChanged.connect(self._render_selected)
        self.start_button.clicked.connect(self.start_requested.emit)
        self.resume_button.clicked.connect(self._resume)
        self.interrupt_button.clicked.connect(self._interrupt)
        self.view_records_button.clicked.connect(self._view_records)
        self.export_button.clicked.connect(self._export)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Give the detail workspace more room only when the window is genuinely wide."""
        super().resizeEvent(event)
        wide = event.size().width() >= 1500
        if wide == self._wide_layout:
            return
        self._wide_layout = wide
        available = max(event.size().width() - 32, 1)
        list_ratio = 0.42 if wide else 0.62
        list_width = int(available * list_ratio)
        self.splitter.setSizes((list_width, available - list_width))

    @Slot()
    def refresh(self) -> None:
        started_from, started_to = self.date_range.values()
        self._runs = self._repository.search_runs(
            self.query_input.text(),
            operator=self.operator_input.text(),
            status=self._status_filter(),
            started_from=started_from,
            started_to=started_to,
        )
        self.run_table.setRowCount(len(self._runs))
        self.run_count_chip.setText(f"{len(self._runs)} 个")
        for row, run in enumerate(self._runs):
            values = (
                run.run_id,
                f"{run.configuration.product_code}/{run.configuration.version}",
                run.operator,
                run.status.value,
                f"{run.completed_stations}/{run.total_stations}",
                display_datetime(run.started_at),
            )
            for column, value in enumerate(values):
                self.run_table.setItem(row, column, readable_item(value))
        if self._runs:
            self.run_table.selectRow(0)
            # Qt does not emit itemSelectionChanged when row 0 was already selected
            # before the refresh.  Render explicitly so the snapshot and actions
            # always describe the newly loaded first row.
            self._render_selected()
            self._show_success(
                f"找到 {len(self._runs)} 个运行 · 更新于 {self._clock():%H:%M}"
            )
        else:
            self.run_summary_title.setText("没有匹配的生产运行")
            self.run_status_chip.setText("状态 -")
            self.run_progress_chip.setText("0 / 0")
            self.run_ng_chip.setText("NG 0")
            self.snapshot_label.setText("没有匹配的生产运行")
            self.station_table.setRowCount(0)
            self.attempt_table.setRowCount(0)
            self.attempt_summary_label.setText("扫码记录：0 条")
            self.resume_button.setEnabled(False)
            self.interrupt_button.setEnabled(False)
            self.view_records_button.setEnabled(False)
            self.export_button.setEnabled(False)
            set_feedback(
                self.status_label,
                "neutral",
                f"没有匹配的生产运行 · 更新于 {self._clock():%H:%M}",
            )

    @Slot()
    def _render_selected(self) -> None:
        run = self._selected()
        if run is None:
            return
        self.run_summary_title.setText(run.run_id)
        status_text, status_style = {
            RunStatus.RUNNING: ("运行中", "background: #ecfdf3; color: #067647;"),
            RunStatus.COMPLETED: ("已完成", "background: #eff8ff; color: #175cd3;"),
            RunStatus.INTERRUPTED: ("已中断", "background: #fef3f2; color: #d92d20;"),
        }[run.status]
        self.run_status_chip.setText(status_text)
        self.run_status_chip.setStyleSheet(status_style)
        self.run_progress_chip.setText(
            f"{run.completed_stations} / {run.total_stations}"
        )
        self.snapshot_label.setText(
            f"配置快照：{run.configuration.product_code}/{run.configuration.version}\n"
            f"BOM 版本 ID：{run.configuration.bom_version_id or '-'}\n"
            f"启动操作员：{run.operator} | 状态：{run.status.value}\n"
            f"开始时间：{display_datetime(run.started_at)}\n"
            f"结束/中断：{display_datetime(run.completed_at or run.interrupted_at) or '-'}\n"
            f"中断原因：{run.interruption_reason or '-'}"
        )
        states = self._repository.list_station_states(run.run_id)
        self.station_table.setRowCount(len(states))
        for row, state in enumerate(states):
            values = (
                state.device_code,
                state.station_code,
                state.expected_material,
                "已完成" if state.completed else "待扫码",
                display_datetime(state.completed_at),
            )
            for column, value in enumerate(values):
                self.station_table.setItem(row, column, readable_item(value))
        attempts = self._repository.list_for_run(run.run_id)
        self.attempt_table.setRowCount(len(attempts))
        ng_count = 0
        repeated_count = 0
        for row, attempt in enumerate(attempts):
            if attempt.result.value == "NG":
                ng_count += 1
            if attempt.repeated:
                repeated_count += 1
            values = (
                display_datetime(attempt.timestamp),
                attempt.device_code,
                attempt.station_code,
                attempt.expected_material,
                attempt.scanned_material,
                attempt.result.value,
                "是" if attempt.repeated else "否",
            )
            for column, value in enumerate(values):
                self.attempt_table.setItem(row, column, readable_item(value))
        self.attempt_summary_label.setText(
            f"扫码记录：{len(attempts)} 条 · NG {ng_count} · 重复 {repeated_count}"
        )
        self.run_ng_chip.setText(f"NG {ng_count}")
        self.resume_button.setEnabled(run.status is RunStatus.INTERRUPTED)
        self.interrupt_button.setEnabled(run.status is RunStatus.RUNNING)
        self.view_records_button.setEnabled(True)
        self.export_button.setEnabled(self._exporter is not None and bool(attempts))

    @Slot()
    def _resume(self) -> None:
        run = self._selected()
        if run is None:
            self._show_error("请先选择生产运行")
            return
        if run.status is not RunStatus.INTERRUPTED:
            self._show_error("只有已中断运行可以恢复")
            return
        self.resume_requested.emit(run.run_id)
        self._show_success(f"已请求恢复 {run.run_id}")

    @Slot()
    def _interrupt(self) -> None:
        run = self._selected()
        if run is None:
            self._show_error("请先选择生产运行")
            return
        if run.status is not RunStatus.RUNNING:
            self._show_error("只有运行中记录可以中断")
            return
        reason = self.interruption_reason_input.text().strip()
        if not reason:
            self._show_error("中断原因不能为空")
            return
        self.interrupt_requested.emit(run.run_id, reason)
        self._show_success(f"已请求中断 {run.run_id}")

    @Slot()
    def _view_records(self) -> None:
        if self._selected() is None:
            self._show_error("请先选择生产运行")
            return
        self.detail_tabs.setCurrentIndex(1)

    @Slot()
    def _export(self) -> None:
        run = self._selected()
        if run is None:
            self._show_error("请先选择生产运行")
            return
        if self._exporter is None:
            self._show_error("当前未配置导出功能")
            return
        path_text, _ = QFileDialog.getSaveFileName(
            self,
            "导出扫码记录",
            f"{run.run_id}.csv",
            "CSV 文件 (*.csv)",
        )
        if not path_text:
            return
        try:
            self._exporter.export_run(run.run_id, Path(path_text))
        except (OSError, ValueError) as error:
            self._show_error(str(error))
            self._announcer.announce(VoicePrompt.EXPORT_FAILED)
            return
        self._show_success(f"已导出 {run.run_id} 到 {path_text}")
        self._announcer.announce(VoicePrompt.RECORDS_EXPORTED)

    def _selected(self) -> ProductionRun | None:
        row = self.run_table.currentRow()
        return self._runs[row] if 0 <= row < len(self._runs) else None

    def _status_filter(self) -> RunStatus | None:
        return {
            0: None,
            1: RunStatus.RUNNING,
            2: RunStatus.COMPLETED,
            3: RunStatus.INTERRUPTED,
        }[self.status_combo.currentIndex()]

    def _show_success(self, message: str) -> None:
        set_feedback(self.status_label, "success", message)

    def _show_error(self, message: str) -> None:
        set_feedback(self.status_label, "error", message)
