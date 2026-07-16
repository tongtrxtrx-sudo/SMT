"""Operator scanning screen for material verification runs."""

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal, Slot
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

from smt_guard.feedback import (
    SCAN_STEP_PROMPTS,
    AnnouncementSink,
    AudioSink,
    FeedbackState,
    SilentAnnouncementSink,
    VisualIntent,
    VoicePrompt,
)
from smt_guard.records import Attempt
from smt_guard.run import AttemptSink, ProductionRun, RunPersistence, VerificationRun
from smt_guard.scan import ProductConfiguration, ScanStep
from smt_guard.ui.formatting import display_datetime


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

    import_requested = Signal()

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
        announcer: AnnouncementSink | None = None,
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
        self._announcer = announcer or SilentAnnouncementSink()
        self._configurations: list[ProductConfiguration] = []
        self._run: VerificationRun | None = None
        self._build_ui()
        self._connect_signals()
        self.refresh_configurations()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        title = QLabel("扫码作业")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        run_form = QFormLayout()
        self.configuration_combo = QComboBox()
        self.start_button = QPushButton("开始新运行")
        self.start_button.setProperty("actionRole", "primary")
        run_form.addRow("产品配置", self.configuration_combo)
        run_form.addRow("", self.start_button)
        layout.addLayout(run_form)
        self.import_configuration_button = QPushButton("没有可用配置，前往导入配置")
        self.import_configuration_button.setProperty("actionRole", "primary")
        self.import_configuration_button.hide()
        layout.addWidget(self.import_configuration_button)

        self.run_label = QLabel("运行：未开始")
        layout.addWidget(self.run_label)

        self.scanner_status_button = QPushButton("扫码枪等待运行")
        self.scanner_status_button.setEnabled(False)
        self.scanner_status_button.setToolTip("扫码输入框获得焦点后即可接收扫码枪输入")
        layout.addWidget(self.scanner_status_button, 0, Qt.AlignmentFlag.AlignHCenter)

        self.feedback_label = QLabel("请先开始运行")
        self.feedback_label.setObjectName("scanFeedback")
        self.feedback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feedback_label.setMinimumHeight(150)
        self.feedback_label.setWordWrap(True)
        layout.addWidget(self.feedback_label)
        self.step_label = QLabel("设备 1  →  站位 2  →  物料 3")
        self.step_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.step_label.setStyleSheet("color: #667085;")
        layout.addWidget(self.step_label)

        scan_row = QHBoxLayout()
        self.scan_input = QLineEdit()
        self.scan_input.setPlaceholderText("扫码后自动提交；也可手动输入后按 Enter")
        self.scan_input.setEnabled(False)
        self.scan_input.installEventFilter(self)
        self.submit_button = QPushButton("手动提交")
        self.submit_button.setToolTip("仅用于键盘调试；扫码枪发送 Enter 时会自动提交")
        self.submit_button.setEnabled(False)
        scan_row.addWidget(self.scan_input, 1)
        scan_row.addWidget(self.submit_button)
        layout.addLayout(scan_row)

        self.expected_label = QLabel("要求物料：-")
        self.scanned_label = QLabel("扫码物料：-")
        self.expected_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.scanned_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.expected_label.hide()
        self.scanned_label.hide()
        layout.addWidget(self.expected_label)
        layout.addWidget(self.scanned_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%v / %m")
        layout.addWidget(self.progress_bar)

        history_row = QHBoxLayout()
        history_row.addWidget(QLabel("最近扫码记录"))
        history_row.addStretch(1)
        self.history_button = QPushButton("展开")
        self.history_button.setCheckable(True)
        history_row.addWidget(self.history_button)
        layout.addLayout(history_row)

        self.attempt_table = QTableWidget(0, 7)
        self.attempt_table.setHorizontalHeaderLabels(
            ("时间", "设备", "站位", "要求物料", "扫码物料", "结果", "重复")
        )
        self.attempt_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.attempt_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.attempt_table.verticalHeader().setVisible(False)
        self.attempt_table.setVisible(False)
        layout.addWidget(self.attempt_table, 1)

    def _connect_signals(self) -> None:
        self.start_button.clicked.connect(self._start_run)
        self.submit_button.clicked.connect(self._submit_scan)
        self.scan_input.returnPressed.connect(self._submit_scan)
        self.scanner_status_button.clicked.connect(self.focus_scanner)
        self.history_button.toggled.connect(self._toggle_history)
        self.import_configuration_button.clicked.connect(self.import_requested.emit)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.scan_input:
            if event.type() == QEvent.Type.FocusIn and self.scan_input.isEnabled():
                self._set_scanner_status("ready")
            elif event.type() == QEvent.Type.FocusOut and self.scan_input.isEnabled():
                QTimer.singleShot(0, self._show_unfocused_warning)
        return super().eventFilter(watched, event)

    @Slot(bool)
    def _toggle_history(self, expanded: bool) -> None:
        self.attempt_table.setVisible(expanded)
        self.history_button.setText("收起" if expanded else "展开")

    @Slot()
    def refresh_configurations(self) -> None:
        self._configurations = self._configuration_source.list_configurations()
        self.configuration_combo.clear()
        for configuration in self._configurations:
            self.configuration_combo.addItem(
                f"{configuration.product_code} / {configuration.version}"
            )
        has_configurations = bool(self._configurations)
        self.configuration_combo.setEnabled(has_configurations)
        self.start_button.setEnabled(has_configurations)
        self.import_configuration_button.setVisible(not has_configurations)
        if self._run is None:
            self.feedback_label.setText(
                "请选择产品配置并开始运行"
                if has_configurations
                else "没有可用配置，请前往导入配置"
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
        previous_run = self._run
        replaced_running = previous_run is not None and not previous_run.completed
        if replaced_running and previous_run is not None:
            previous_run.interrupt("开始新的生产运行")
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
        self._render_feedback(self._run.initial_feedback)
        self._announce_scan_step()
        self.run_changed.emit()
        QTimer.singleShot(0, self.focus_scanner)

    def interrupt_active_run(self, reason: str) -> None:
        """Persist an unfinished active run before the UI is replaced or closed."""
        if self._run is not None and not self._run.completed:
            self._run.interrupt(reason)
            self._run = None
            self._set_scan_controls_enabled(False)
            if reason != "应用关闭":
                self._announcer.announce(VoicePrompt.RUN_INTERRUPTED)
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
        self._render_feedback(self._run.initial_feedback)
        self._announce_scan_step()
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
                self._set_scan_controls_enabled(False)
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
        self._announcer.announce(VoicePrompt.RUN_INTERRUPTED)
        self.run_changed.emit()

    @Slot()
    def focus_scanner(self) -> None:
        """Focus keyboard-wedge input when an active run is ready."""
        if self.scan_input.isEnabled():
            self.scan_input.setFocus()
            self._set_scanner_status("ready")

    def _show_unfocused_warning(self) -> None:
        if self.scan_input.isEnabled() and not self.scan_input.hasFocus():
            self._set_scanner_status("warning")

    @Slot()
    def _submit_scan(self) -> None:
        if self._run is None:
            self._show_message("请先开始运行", "error")
            self._announcer.announce(VoicePrompt.SCAN_REJECTED)
            return
        if self._run.completed:
            self._set_scan_controls_enabled(False)
            self._show_message("全部对料完成", "ok")
            return
        code = self.scan_input.text().strip()
        if not code:
            self._show_message("扫码内容不能为空", "error")
            self._announcer.announce(VoicePrompt.SCAN_REJECTED)
            QTimer.singleShot(0, self.focus_scanner)
            return
        update = self._run.handle_scan(code)
        self.scan_input.clear()
        self._render_feedback(update.feedback)
        if not update.outcome.accepted:
            self._announcer.announce(VoicePrompt.SCAN_REJECTED)
        elif update.attempt is None:
            self._announce_scan_step()
        if update.attempt is not None:
            if update.feedback.complete:
                self._announcer.announce(VoicePrompt.RUN_COMPLETED)
            elif update.feedback.intent is VisualIntent.OK:
                self._announce_scan_step()
            else:
                self._announcer.announce(VoicePrompt.MATERIAL_NG)
            self._refresh_attempts()
            self.run_changed.emit()
        if not update.feedback.complete:
            QTimer.singleShot(0, self.focus_scanner)

    def _announce_scan_step(self) -> None:
        if self._run is not None and not self._run.completed:
            self._announcer.announce(SCAN_STEP_PROMPTS[self._run.current_step])

    def _render_feedback(self, state: FeedbackState) -> None:
        feedback_state = {
            VisualIntent.NEUTRAL: "neutral",
            VisualIntent.OK: "ok",
            VisualIntent.NG: "ng",
        }[state.intent]
        message = "全部对料完成" if state.complete else state.message.replace("请扫描", "请扫码")
        self._show_message(message, feedback_state)
        self.expected_label.setText(f"要求物料：{state.expected_material or '-'}")
        self.scanned_label.setText(f"扫码物料：{state.scanned_material or '-'}")
        show_material = (
            state.intent is VisualIntent.NG
            or (
                self._run is not None
                and not state.complete
                and self._run.current_step is ScanStep.MATERIAL
            )
        )
        self.expected_label.setVisible(show_material)
        self.scanned_label.setVisible(show_material)
        self._render_step_indicator()
        self.progress_bar.setValue(state.completed_stations)
        self._set_scan_controls_enabled(
            self._run is not None and not self._run.completed and not state.complete
        )

    def _set_scan_controls_enabled(self, enabled: bool) -> None:
        """Keep scanner input and submission in one lifecycle state."""
        self.scan_input.setEnabled(enabled)
        self.submit_button.setEnabled(enabled)
        self.scanner_status_button.setEnabled(enabled)
        self._set_scanner_status("warning" if enabled else "inactive")
        if not enabled:
            self.scan_input.clear()

    def _refresh_attempts(self) -> None:
        if self._run is None:
            return
        attempts = self._attempts.list_for_run(self._run.run_id)
        self.attempt_table.setRowCount(len(attempts))
        for row, attempt in enumerate(attempts):
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
                self.attempt_table.setItem(row, column, QTableWidgetItem(value))

    def _show_message(self, message: str, state: str) -> None:
        step = self._run.current_step if self._run is not None else None
        if state == "neutral":
            palette = {
                ScanStep.DEVICE: ("#eff8ff", "#2e90fa", "#175cd3"),
                ScanStep.STATION: ("#fffaeb", "#f79009", "#b54708"),
                ScanStep.MATERIAL: ("#ecfdf3", "#12b76a", "#067647"),
                None: ("#ffffff", "#d0d5dd", "#344054"),
            }[step]
        elif state == "ok":
            palette = ("#dcfae6", "#12b76a", "#05603a")
        else:
            palette = ("#fef3f2", "#f04438", "#b42318")
        background, border, color = palette
        self.feedback_label.setProperty("feedbackState", state)
        self.feedback_label.setStyleSheet(
            f"color: {color}; background-color: {background}; "
            f"border: 3px solid {border}; border-radius: 12px;"
        )
        self.feedback_label.setText(message)

    def _render_step_indicator(self) -> None:
        if self._run is None or self._run.completed:
            self.step_label.setText("设备 1  →  站位 2  →  物料 3")
            return
        labels = {
            ScanStep.DEVICE: "● 设备 1  →  站位 2  →  物料 3",
            ScanStep.STATION: "设备 1  →  ● 站位 2  →  物料 3",
            ScanStep.MATERIAL: "设备 1  →  站位 2  →  ● 物料 3",
        }
        colors = {
            ScanStep.DEVICE: "#175cd3",
            ScanStep.STATION: "#b54708",
            ScanStep.MATERIAL: "#067647",
        }
        self.step_label.setText(labels[self._run.current_step])
        self.step_label.setStyleSheet(
            f"color: {colors[self._run.current_step]}; font-weight: 600;"
        )

    def _set_scanner_status(self, state: str) -> None:
        text, style = {
            "ready": (
                "● 扫码枪已就绪",
                "color: #067647; background: #ecfdf3; border: 1px solid #75e0a7;",
            ),
            "warning": (
                "扫码输入未激活，点击此处恢复",
                "color: #b54708; background: #fffaeb; border: 1px solid #fec84b;",
            ),
            "inactive": (
                "扫码枪等待运行",
                "color: #667085; background: #f2f4f7; border: 1px solid #d0d5dd;",
            ),
        }[state]
        self.scanner_status_button.setText(text)
        self.scanner_status_button.setStyleSheet(style + " padding: 6px 14px;")

    def _current_operator(self) -> str:
        if self._operator_provider is not None:
            return self._operator_provider()
        return self._operator
    run_changed = Signal()
