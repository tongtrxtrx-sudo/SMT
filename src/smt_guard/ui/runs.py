"""Production run query and recovery page."""

from datetime import datetime
from typing import Protocol

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from smt_guard.run import ProductionRun, RunStationState, RunStatus
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


class ProductionRunManagementWidget(QWidget):
    """Search run snapshots and request scanner start or recovery."""

    start_requested = Signal()
    resume_requested = Signal(str)
    interrupt_requested = Signal(str, str)

    def __init__(self, repository: ProductionRunReader, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repository = repository
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
        self.started_from_input = QLineEdit()
        self.started_from_input.setPlaceholderText("开始时间自（ISO，可选）")
        self.started_to_input = QLineEdit()
        self.started_to_input.setPlaceholderText("开始时间至（ISO，可选）")
        self.query_button = QPushButton("查询")
        for widget in (
            self.query_input,
            self.operator_input,
            self.status_combo,
            self.started_from_input,
            self.started_to_input,
            self.query_button,
        ):
            filters.addWidget(widget)
        layout.addLayout(filters)

        splitter = QSplitter()
        self.run_table = QTableWidget(0, 9)
        self.run_table.setHorizontalHeaderLabels(
            ("运行号", "产品", "版本", "操作员", "状态", "进度", "开始", "结束/中断", "原因")
        )
        self.run_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.run_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.run_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.run_table.verticalHeader().setVisible(False)
        set_column_widths(
            self.run_table,
            (220, 120, 160, 110, 90, 80, 190, 190, 180),
        )
        splitter.addWidget(self.run_table)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.snapshot_label = QLabel("请选择生产运行")
        self.snapshot_label.setWordWrap(True)
        right_layout.addWidget(self.snapshot_label)
        self.station_table = QTableWidget(0, 5)
        self.station_table.setHorizontalHeaderLabels(
            ("设备", "站位", "要求物料", "状态", "完成时间")
        )
        self.station_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        set_column_widths(self.station_table, (130, 120, 220, 90, 190))
        right_layout.addWidget(self.station_table, 1)
        splitter.addWidget(right)
        splitter.setSizes((750, 450))
        layout.addWidget(splitter, 1)

        actions = QHBoxLayout()
        self.start_button = QPushButton("转到扫码开始")
        self.resume_button = QPushButton("恢复所选运行")
        self.interruption_reason_input = QLineEdit("人工中断")
        self.interrupt_button = QPushButton("中断所选运行")
        self.refresh_button = QPushButton("刷新")
        actions.addWidget(self.start_button)
        actions.addWidget(self.resume_button)
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
        self.run_table.itemSelectionChanged.connect(self._render_selected)
        self.start_button.clicked.connect(self.start_requested.emit)
        self.resume_button.clicked.connect(self._resume)
        self.interrupt_button.clicked.connect(self._interrupt)

    @Slot()
    def refresh(self) -> None:
        try:
            started_from = self._parse_time(self.started_from_input.text())
            started_to = self._parse_time(self.started_to_input.text())
            self._runs = self._repository.search_runs(
                self.query_input.text(),
                operator=self.operator_input.text(),
                status=self._status_filter(),
                started_from=started_from,
                started_to=started_to,
            )
        except ValueError as error:
            self._show_error(str(error))
            return
        self.run_table.setRowCount(len(self._runs))
        for row, run in enumerate(self._runs):
            ended = run.completed_at or run.interrupted_at
            values = (
                run.run_id,
                run.configuration.product_code,
                run.configuration.version,
                run.operator,
                run.status.value,
                f"{run.completed_stations}/{run.total_stations}",
                run.started_at.isoformat(),
                "" if ended is None else ended.isoformat(),
                run.interruption_reason,
            )
            for column, value in enumerate(values):
                self.run_table.setItem(row, column, readable_item(value))
        if self._runs:
            self.run_table.selectRow(0)
            # Qt does not emit itemSelectionChanged when row 0 was already selected
            # before the refresh.  Render explicitly so the snapshot and actions
            # always describe the newly loaded first row.
            self._render_selected()
            self._show_success(f"找到 {len(self._runs)} 个运行")
        else:
            self.snapshot_label.setText("没有匹配的生产运行")
            self.station_table.setRowCount(0)
            self.resume_button.setEnabled(False)
            self.interrupt_button.setEnabled(False)
            self.status_label.setText("没有匹配的生产运行")

    @Slot()
    def _render_selected(self) -> None:
        run = self._selected()
        if run is None:
            return
        self.snapshot_label.setText(
            f"配置快照：{run.configuration.product_code}/{run.configuration.version}\n"
            f"BOM 版本 ID：{run.configuration.bom_version_id or '-'}\n"
            f"启动操作员：{run.operator} | 状态：{run.status.value}"
        )
        states = self._repository.list_station_states(run.run_id)
        self.station_table.setRowCount(len(states))
        for row, state in enumerate(states):
            values = (
                state.device_code,
                state.station_code,
                state.expected_material,
                "已完成" if state.completed else "待扫码",
                "" if state.completed_at is None else state.completed_at.isoformat(),
            )
            for column, value in enumerate(values):
                self.station_table.setItem(row, column, readable_item(value))
        self.resume_button.setEnabled(run.status is RunStatus.INTERRUPTED)
        self.interrupt_button.setEnabled(run.status is RunStatus.RUNNING)

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

    @staticmethod
    def _parse_time(value: str) -> datetime | None:
        text = value.strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text)
        except ValueError as error:
            raise ValueError(f"无效 ISO 时间：{text}") from error

    def _show_success(self, message: str) -> None:
        self.status_label.setStyleSheet("color: #18794e;")
        self.status_label.setText(message)

    def _show_error(self, message: str) -> None:
        self.status_label.setStyleSheet("color: #b42318;")
        self.status_label.setText(message)
