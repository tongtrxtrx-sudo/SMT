"""Operator scanning screen for material verification runs."""

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QBoxLayout,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
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
from smt_guard.ui.tables import set_column_widths, set_responsive_columns


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
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(12)
        title = QLabel("扫码作业")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        self.selection_card = QFrame()
        self.selection_card.setObjectName("selectionCard")
        selection_layout = QHBoxLayout(self.selection_card)
        selection_layout.setContentsMargins(14, 10, 14, 10)
        selection_layout.addWidget(QLabel("产品配置"))
        self.configuration_combo = QComboBox()
        self.configuration_combo.setMinimumWidth(260)
        self.configuration_combo.setMaximumWidth(900)
        self.start_button = QPushButton("开始新运行")
        self.start_button.setProperty("actionRole", "primary")
        self.import_configuration_button = QPushButton("没有可用配置，前往导入配置")
        self.import_configuration_button.setProperty("actionRole", "primary")
        self.import_configuration_button.hide()
        selection_layout.addWidget(self.configuration_combo, 1)
        selection_layout.addWidget(self.start_button)
        selection_layout.addWidget(self.import_configuration_button)
        selection_layout.addStretch(1)
        layout.addWidget(self.selection_card)

        self.product_summary_label = QLabel("产品：未选择")
        self.product_summary_label.setObjectName("productSummary")
        layout.addWidget(self.product_summary_label)
        self.run_label = QLabel("运行：未开始")
        self.run_label.setStyleSheet("color: #667085;")
        layout.addWidget(self.run_label)

        self.workflow_host = QWidget()
        self.workflow_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        self.workflow_layout.setContentsMargins(0, 0, 0, 0)
        self.workflow_layout.setSpacing(12)
        self.workflow_host.setLayout(self.workflow_layout)

        self.hero_column = QWidget()
        hero_column_layout = QVBoxLayout(self.hero_column)
        hero_column_layout.setContentsMargins(0, 0, 0, 0)
        hero_column_layout.setSpacing(10)
        self.hero_card = QFrame()
        self.hero_card.setObjectName("scanHero")
        self.hero_card.setMinimumHeight(230)
        hero_layout = QVBoxLayout(self.hero_card)
        hero_layout.setContentsMargins(22, 18, 22, 18)
        hero_layout.setSpacing(10)
        self.scanner_status_button = QPushButton("扫码枪等待运行")
        self.scanner_status_button.setEnabled(False)
        self.scanner_status_button.setToolTip("扫码输入框获得焦点后即可接收扫码枪输入")
        hero_layout.addWidget(
            self.scanner_status_button, 0, Qt.AlignmentFlag.AlignHCenter
        )

        self.feedback_label = QLabel("请先开始运行")
        self.feedback_label.setObjectName("scanFeedback")
        self.feedback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feedback_label.setMinimumHeight(170)
        self.feedback_label.setMaximumHeight(310)
        self.feedback_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.feedback_label.setWordWrap(True)
        hero_layout.addWidget(self.feedback_label, 1)
        self.step_label = QLabel("设备 1  →  站位 2  →  物料 3")
        self.step_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.step_label.setStyleSheet("color: #667085;")
        hero_layout.addWidget(self.step_label)

        self.material_panel = QWidget()
        material_row = QHBoxLayout(self.material_panel)
        material_row.setContentsMargins(0, 0, 0, 0)
        material_row.setSpacing(18)
        self.expected_label = QLabel("要求物料：-")
        self.scanned_label = QLabel("扫码物料：-")
        self.expected_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.scanned_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        material_row.addStretch(1)
        material_row.addWidget(self.expected_label)
        material_row.addWidget(self.scanned_label)
        material_row.addStretch(1)
        self.material_panel.hide()
        hero_layout.addWidget(self.material_panel)
        hero_column_layout.addWidget(self.hero_card, 1)

        self.input_card = QFrame()
        self.input_card.setObjectName("scanInputCard")
        self.input_card.setMinimumHeight(82)
        scan_row = QHBoxLayout()
        scan_row.setContentsMargins(12, 12, 12, 12)
        self.scan_input = QLineEdit()
        self.scan_input.setPlaceholderText("请在这里扫码；扫码枪发送 Enter 后自动提交")
        self.scan_input.setMinimumHeight(56)
        self.scan_input.setStyleSheet("font-size: 18px; padding: 0 14px;")
        self.scan_input.setEnabled(False)
        self.scan_input.installEventFilter(self)
        self.submit_button = QPushButton("手动提交")
        self.submit_button.setToolTip("仅用于键盘调试；扫码枪发送 Enter 时会自动提交")
        self.submit_button.setMinimumHeight(56)
        self.submit_button.setEnabled(False)
        scan_row.addWidget(self.scan_input, 1)
        scan_row.addWidget(self.submit_button)
        self.input_card.setLayout(scan_row)
        hero_column_layout.addWidget(self.input_card)
        self.workflow_layout.addWidget(self.hero_column)

        self.overview_column = QWidget()
        overview_layout = QVBoxLayout(self.overview_column)
        overview_layout.setContentsMargins(0, 0, 0, 0)
        overview_layout.setSpacing(10)
        self.progress_card = QFrame()
        self.progress_card.setObjectName("contentCard")
        self.progress_card.setMinimumHeight(68)
        progress_layout = QHBoxLayout(self.progress_card)
        progress_layout.setContentsMargins(14, 10, 14, 10)
        progress_layout.setSpacing(14)
        progress_title = QLabel("本次进度")
        progress_title.setObjectName("sectionTitle")
        progress_layout.addWidget(progress_title)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(22)
        progress_layout.addWidget(self.progress_bar, 1)
        self.progress_count_label = QLabel("0 / 0")
        self.progress_count_label.setObjectName("progressCount")
        self.progress_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_count_label.setMinimumWidth(110)
        progress_layout.addWidget(self.progress_count_label)
        overview_layout.addWidget(self.progress_card)

        self.history_card = QFrame()
        self.history_card.setObjectName("historyCard")
        history_layout = QVBoxLayout(self.history_card)
        history_layout.setContentsMargins(12, 8, 12, 8)
        history_row = QHBoxLayout()
        history_row.addWidget(QLabel("最近扫码记录"))
        history_row.addStretch(1)
        self.history_button = QPushButton("展开")
        self.history_button.setCheckable(True)
        history_row.addWidget(self.history_button)
        history_layout.addLayout(history_row)

        self.attempt_table = QTableWidget(0, 7)
        self.attempt_table.setHorizontalHeaderLabels(
            ("时间", "设备", "站位", "要求物料", "扫码物料", "结果", "重复")
        )
        self.attempt_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.attempt_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.attempt_table.verticalHeader().setVisible(False)
        set_column_widths(self.attempt_table, (145, 90, 90, 150, 150, 65, 60))
        set_responsive_columns(
            self.attempt_table,
            stretch=(0, 1, 2, 3, 4),
            compact=(5, 6),
        )
        self.attempt_table.setVisible(False)
        history_layout.addWidget(self.attempt_table, 1)
        overview_layout.addWidget(self.history_card, 1)
        self.workflow_layout.addWidget(self.overview_column)
        layout.addWidget(self.workflow_host, 1)
        self._history_user_overridden = False
        self._wide_layout: bool | None = None
        self._apply_responsive_layout(self.width())

    def _connect_signals(self) -> None:
        self.start_button.clicked.connect(self._start_run)
        self.submit_button.clicked.connect(self._submit_scan)
        self.scan_input.returnPressed.connect(self._submit_scan)
        self.scanner_status_button.clicked.connect(self.focus_scanner)
        self.history_button.toggled.connect(self._toggle_history)
        self.history_button.clicked.connect(self._remember_history_override)
        self.import_configuration_button.clicked.connect(self.import_requested.emit)
        self.configuration_combo.currentTextChanged.connect(
            self._update_product_summary
        )

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
        self.history_card.setMaximumHeight(16777215 if expanded else 82)

    @Slot(bool)
    def _remember_history_override(self, _expanded: bool) -> None:
        self._history_user_overridden = True

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Reflow the primary task and overview at shop-floor full-screen widths."""
        super().resizeEvent(event)
        self._apply_responsive_layout(event.size().width())

    def _apply_responsive_layout(self, width: int) -> None:
        wide = width >= 1400
        if wide == self._wide_layout:
            return
        self._wide_layout = wide
        self.workflow_layout.setDirection(QBoxLayout.Direction.TopToBottom)
        self.workflow_layout.setStretch(0, 0)
        self.workflow_layout.setStretch(1, 1)
        self.hero_card.setMinimumHeight(320 if wide else 220)
        self.hero_card.setMaximumHeight(400 if wide else 290)
        self.hero_column.setMaximumHeight(492 if wide else 382)
        self.progress_card.setMaximumHeight(72)
        if not self._history_user_overridden:
            self.history_button.setChecked(wide)
        self.history_card.setMaximumHeight(
            16777215 if self.history_button.isChecked() else 82
        )

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
        self._update_product_summary(self.configuration_combo.currentText())
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
            f"运行：{self._run.run_id} · 进度 0/{len(configuration.assignments)}"
        )
        self.product_summary_label.setText(
            f"产品：{configuration.product_code} / {configuration.version}"
        )
        self.selection_card.hide()
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
            self.selection_card.show()
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
            f"运行：{self._run.run_id} · 进度 "
            f"{self._run.initial_feedback.completed_stations}/"
            f"{len(configuration.assignments)} · 恢复人：{operator}"
        )
        self.product_summary_label.setText(
            f"产品：{configuration.product_code} / {configuration.version}"
        )
        self.selection_card.hide()
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
                self.selection_card.show()
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
        self.material_panel.setVisible(show_material)
        self._render_step_indicator()
        self.progress_bar.setValue(state.completed_stations)
        self.progress_count_label.setText(
            f"{state.completed_stations} / {self.progress_bar.maximum()}"
        )
        if self._run is not None:
            self.run_label.setText(
                f"运行：{self._run.run_id} · 进度 "
                f"{state.completed_stations}/{self.progress_bar.maximum()}"
            )
        if state.complete:
            self.selection_card.show()
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

    @Slot(str)
    def _update_product_summary(self, configuration: str) -> None:
        if self._run is None:
            self.product_summary_label.setText(
                f"产品：{configuration}" if configuration else "产品：未选择"
            )
    run_changed = Signal()
