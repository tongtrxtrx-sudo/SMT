"""Production run query and recovery page."""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
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
from smt_guard.ui.date_range import DateRangeFilter
from smt_guard.ui.formatting import display_datetime
from smt_guard.ui.tables import readable_item, set_column_widths


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
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("生产运行管理")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        filters = QHBoxLayout()
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("运行号、产品或版本")
        self.operator_input = QLineEdit()
        self.operator_input.setPlaceholderText("操作员")
        self.status_combo = QComboBox()
        self.status_combo.addItems(("全部状态", "运行中", "已完成", "已中断"))
        self.query_button = QPushButton("查询")
        self.query_button.setProperty("actionRole", "primary")
        for widget in (
            self.query_input,
            self.operator_input,
            self.status_combo,
            self.query_button,
        ):
            filters.addWidget(widget)
        layout.addLayout(filters)
        self.date_range = DateRangeFilter(clock=self._clock, default_days=7)
        self.started_from_input = self.date_range.started_from_input
        self.started_to_input = self.date_range.started_to_input
        layout.addWidget(self.date_range)

        splitter = QSplitter()
        self.run_table = QTableWidget(0, 6)
        self.run_table.setHorizontalHeaderLabels(
            ("运行号", "产品 / 版本", "操作员", "状态", "进度", "开始时间")
        )
        self.run_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.run_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.run_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.run_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.run_table.verticalHeader().setVisible(False)
        set_column_widths(
            self.run_table,
            (160, 170, 90, 80, 70, 140),
        )
        self.run_table.horizontalHeader().setStretchLastSection(True)
        splitter.addWidget(self.run_table)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.snapshot_label = QLabel("请选择生产运行")
        self.snapshot_label.setWordWrap(True)
        right_layout.addWidget(self.snapshot_label)
        self.detail_tabs = QTabWidget()
        self.station_table = QTableWidget(0, 5)
        self.station_table.setHorizontalHeaderLabels(
            ("设备", "站位", "要求物料", "状态", "完成时间")
        )
        self.station_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.station_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        set_column_widths(self.station_table, (65, 50, 110, 55, 95))
        self.station_table.horizontalHeader().setStretchLastSection(True)
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
        self.attempt_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.attempt_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.attempt_table.verticalHeader().setVisible(False)
        set_column_widths(self.attempt_table, (150, 100, 100, 170, 170, 70, 70))
        attempts_layout.addWidget(self.attempt_table, 1)
        self.detail_tabs.addTab(attempts_page, "扫码记录")
        right_layout.addWidget(self.detail_tabs, 1)
        splitter.addWidget(right)
        splitter.setSizes((750, 450))
        layout.addWidget(splitter, 1)

        actions = QHBoxLayout()
        self.start_button = QPushButton("转到扫码开始")
        self.start_button.setProperty("actionRole", "primary")
        self.resume_button = QPushButton("恢复所选运行")
        self.resume_button.setProperty("actionRole", "success")
        self.view_records_button = QPushButton("查看扫码记录")
        self.export_button = QPushButton("导出 CSV")
        self.interruption_reason_input = QLineEdit("人工中断")
        self.interrupt_button = QPushButton("中断所选运行")
        self.interrupt_button.setProperty("actionRole", "danger")
        self.refresh_button = QPushButton("刷新")
        actions.addWidget(self.start_button)
        actions.addWidget(self.resume_button)
        actions.addWidget(self.view_records_button)
        actions.addWidget(self.export_button)
        actions.addWidget(self.interruption_reason_input)
        actions.addWidget(self.interrupt_button)
        actions.addWidget(self.refresh_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        self.status_label = QLabel("就绪")
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
            self.snapshot_label.setText("没有匹配的生产运行")
            self.station_table.setRowCount(0)
            self.attempt_table.setRowCount(0)
            self.attempt_summary_label.setText("扫码记录：0 条")
            self.resume_button.setEnabled(False)
            self.interrupt_button.setEnabled(False)
            self.view_records_button.setEnabled(False)
            self.export_button.setEnabled(False)
            self.status_label.setText(
                f"没有匹配的生产运行 · 更新于 {self._clock():%H:%M}"
            )

    @Slot()
    def _render_selected(self) -> None:
        run = self._selected()
        if run is None:
            return
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
        self.status_label.setStyleSheet("color: #18794e;")
        self.status_label.setText(message)

    def _show_error(self, message: str) -> None:
        self.status_label.setStyleSheet("color: #b42318;")
        self.status_label.setText(message)
