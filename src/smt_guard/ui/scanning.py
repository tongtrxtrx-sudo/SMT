"""Operator scanning screen for material verification runs."""

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from PySide6.QtCore import QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from smt_guard.feedback import AudioSink, FeedbackState, VisualIntent
from smt_guard.records import Attempt
from smt_guard.run import AttemptSink, ProductionRun, RunPersistence, VerificationRun
from smt_guard.scan import ProductConfiguration


class ConfigurationSource(Protocol):
    """Read configurations available for scanning."""

    def list_configurations(self) -> list[ProductConfiguration]:
        """Return configurations in display order."""
        ...


class AttemptHistory(AttemptSink, Protocol):
    """Append and query attempts for the current run."""

    def list_for_run(self, run_id: str) -> list[Attempt]:
        """Return one run's attempts in identifier order."""
        ...


class RunManagementPersistence(RunPersistence, Protocol):
    def get(self, run_id: str) -> ProductionRun: ...

    def resume(
        self, run_id: str, *, operator: str, resumed_at: datetime
    ) -> ProductionRun: ...

    def completed_station_keys(self, run_id: str) -> set[tuple[str, str]]: ...


class ScanWidget(QWidget):
    """Select a configuration and process keyboard-wedge scanner input."""

    def __init__(
        self,
        configurations: ConfigurationSource,
        attempts: AttemptHistory,
        audio: AudioSink,
        *,
        clock: Callable[[], datetime],
        run_id_factory: Callable[[], str],
        runs: RunManagementPersistence | None = None,
        operator: str = "SYSTEM",
        operator_provider: Callable[[], str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._configuration_source = configurations
        self._attempts = attempts
        self._audio = audio
        self._clock = clock
        self._run_id_factory = run_id_factory
        self._runs = runs
        self._operator = operator.strip() or "SYSTEM"
        self._operator_provider = operator_provider
        self._configurations: list[ProductConfiguration] = []
        self._run: VerificationRun | None = None
        self._build_ui()
        self._connect_signals()
        self.refresh_configurations()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("SMT 扫码防错"))

        run_form = QFormLayout()
        self.configuration_combo = QComboBox()
        self.start_button = QPushButton("开始新运行")
        run_form.addRow("产品配置", self.configuration_combo)
        run_form.addRow("", self.start_button)
        layout.addLayout(run_form)

        self.run_label = QLabel("运行：未开始")
        layout.addWidget(self.run_label)

        scan_row = QHBoxLayout()
        self.scan_input = QLineEdit()
        self.scan_input.setPlaceholderText("扫描设备码、站位码或物料码后按 Enter")
        self.scan_input.setEnabled(False)
        self.submit_button = QPushButton("提交扫码")
        self.submit_button.setEnabled(False)
        scan_row.addWidget(self.scan_input, 1)
        scan_row.addWidget(self.submit_button)
        layout.addLayout(scan_row)

        self.feedback_label = QLabel("请先开始运行")
        self.feedback_label.setObjectName("scanFeedback")
        layout.addWidget(self.feedback_label)
        self.expected_label = QLabel("要求物料：-")
        self.scanned_label = QLabel("扫码物料：-")
        layout.addWidget(self.expected_label)
        layout.addWidget(self.scanned_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.attempt_table = QTableWidget(0, 7)
        self.attempt_table.setHorizontalHeaderLabels(
            ("时间", "设备", "站位", "要求物料", "扫码物料", "结果", "重复")
        )
        self.attempt_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.attempt_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.attempt_table.verticalHeader().setVisible(False)
        layout.addWidget(self.attempt_table, 1)

    def _connect_signals(self) -> None:
        self.start_button.clicked.connect(self._start_run)
        self.submit_button.clicked.connect(self._submit_scan)
        self.scan_input.returnPressed.connect(self._submit_scan)

    @Slot()
    def refresh_configurations(self) -> None:
        self._configurations = self._configuration_source.list_configurations()
        self.configuration_combo.clear()
        for configuration in self._configurations:
            self.configuration_combo.addItem(
                f"{configuration.product_code} / {configuration.version}"
            )

    @Slot()
    def _start_run(self) -> None:
        index = self.configuration_combo.currentIndex()
        if index < 0 or index >= len(self._configurations):
            self._show_message("请先导入产品配置", "error")
            return
        configuration = self._configurations[index]
        try:
            operator = self._current_operator()
        except ValueError as error:
            self._show_message(str(error), "error")
            return
        if self._run is not None and not self._run.completed:
            self._run.interrupt("开始新的生产运行")
        self._run = VerificationRun(
            self._run_id_factory(),
            configuration,
            self._attempts,
            self._audio,
            clock=self._clock,
            runs=self._runs,
            operator=operator,
        )
        self.run_label.setText(
            f"运行：{self._run.run_id} | {configuration.product_code}/{configuration.version}"
        )
        self.progress_bar.setRange(0, len(configuration.assignments))
        self.progress_bar.setValue(0)
        self.attempt_table.setRowCount(0)
        self.scan_input.setEnabled(True)
        self.submit_button.setEnabled(True)
        self._render_feedback(self._run.initial_feedback)
        self.run_changed.emit()
        QTimer.singleShot(0, self.focus_scanner)

    def interrupt_active_run(self, reason: str) -> None:
        """Persist an unfinished active run before the UI is replaced or closed."""
        if self._run is not None and not self._run.completed:
            self._run.interrupt(reason)
            self._run = None
            self.scan_input.setEnabled(False)
            self.submit_button.setEnabled(False)
            self.run_changed.emit()

    def resume_run(self, run_id: str) -> None:
        """Resume one interrupted persisted run into the scanner page."""
        if self._runs is None:
            self._show_message("当前运行仓储不支持恢复", "error")
            return
        try:
            operator = self._current_operator()
            if self._run is not None and not self._run.completed:
                self._run.interrupt("恢复其他生产运行")
            persisted = self._runs.resume(run_id, operator=operator, resumed_at=self._clock())
            self._run = VerificationRun.resume(
                persisted,
                self._attempts,
                self._audio,
                clock=self._clock,
                runs=self._runs,
                completed_stations=self._runs.completed_station_keys(run_id),
                operator=operator,
            )
        except (LookupError, ValueError) as error:
            self._show_message(str(error), "error")
            return
        configuration = self._run.configuration
        self.run_label.setText(
            f"运行：{self._run.run_id} | {configuration.product_code}/{configuration.version} | "
            f"恢复人：{operator}"
        )
        self.progress_bar.setRange(0, len(configuration.assignments))
        self._refresh_attempts()
        self.scan_input.setEnabled(True)
        self.submit_button.setEnabled(True)
        self._render_feedback(self._run.initial_feedback)
        self.run_changed.emit()
        QTimer.singleShot(0, self.focus_scanner)

    def interrupt_run(self, run_id: str, reason: str) -> None:
        """Interrupt a selected running record and clear it if currently scanned."""
        if self._runs is None:
            self._show_message("当前运行仓储不支持中断", "error")
            return
        try:
            operator = self._current_operator()
            if self._run is not None and self._run.run_id == run_id:
                self._run.interrupt(reason)
                self._run = None
                self.scan_input.setEnabled(False)
                self.submit_button.setEnabled(False)
            else:
                self._runs.interrupt(
                    run_id,
                    operator=operator,
                    interrupted_at=self._clock(),
                    reason=reason,
                )
        except (LookupError, ValueError) as error:
            self._show_message(str(error), "error")
            return
        self._show_message(f"已中断运行 {run_id}", "neutral")
        self.run_changed.emit()

    @Slot()
    def focus_scanner(self) -> None:
        """Focus keyboard-wedge input when an active run is ready."""
        if self.scan_input.isEnabled():
            self.scan_input.setFocus()

    @Slot()
    def _submit_scan(self) -> None:
        if self._run is None:
            self._show_message("请先开始运行", "error")
            return
        code = self.scan_input.text().strip()
        if not code:
            self._show_message("扫码内容不能为空", "error")
            return
        update = self._run.handle_scan(code)
        self.scan_input.clear()
        self._render_feedback(update.feedback)
        if update.attempt is not None:
            self._refresh_attempts()
            self.run_changed.emit()

    def _render_feedback(self, state: FeedbackState) -> None:
        feedback_state = {
            VisualIntent.NEUTRAL: "neutral",
            VisualIntent.OK: "ok",
            VisualIntent.NG: "ng",
        }[state.intent]
        self._show_message(state.message, feedback_state)
        self.expected_label.setText(f"要求物料：{state.expected_material or '-'}")
        self.scanned_label.setText(f"扫码物料：{state.scanned_material or '-'}")
        self.progress_bar.setValue(state.completed_stations)

    def _refresh_attempts(self) -> None:
        if self._run is None:
            return
        attempts = self._attempts.list_for_run(self._run.run_id)
        self.attempt_table.setRowCount(len(attempts))
        for row, attempt in enumerate(attempts):
            values = (
                attempt.timestamp.isoformat(),
                attempt.device_code,
                attempt.station_code,
                attempt.expected_material,
                attempt.scanned_material,
                attempt.result.value,
                "是" if attempt.repeated else "否",
            )
            for column, value in enumerate(values):
                self.attempt_table.setItem(row, column, QTableWidgetItem(value))

    def _show_message(self, message: str, state: str) -> None:
        colors = {"neutral": "#344054", "ok": "#18794e", "ng": "#b42318", "error": "#b42318"}
        self.feedback_label.setProperty("feedbackState", state)
        self.feedback_label.setStyleSheet(f"color: {colors[state]};")
        self.feedback_label.setText(message)

    def _current_operator(self) -> str:
        if self._operator_provider is not None:
            return self._operator_provider()
        return self._operator
    run_changed = Signal()
