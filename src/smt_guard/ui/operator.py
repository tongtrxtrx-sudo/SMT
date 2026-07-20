"""Application-wide operator sign-in control."""

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from smt_guard.feedback import AnnouncementSink, SilentAnnouncementSink, VoicePrompt
from smt_guard.operator import OperatorSession


class OperatorSessionWidget(QWidget):
    """Capture the operator used by all subsequent write operations."""

    operator_changed = Signal(str)

    def __init__(
        self,
        session: OperatorSession,
        parent: QWidget | None = None,
        *,
        announcer: AnnouncementSink | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("operatorBar")
        self._session = session
        self._announcer = announcer or SilentAnnouncementSink()
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 8, 6, 8)
        layout.setSpacing(5)
        self.prompt_label = QLabel("当前操作员")
        self.operator_input = QLineEdit(session.operator)
        self.operator_input.setPlaceholderText("请输入工号或姓名")
        self.sign_in_button = QPushButton("确认操作员")
        self.sign_in_button.setProperty("actionRole", "primary")
        self.current_label = QLabel(self._label_text())
        self.current_label.setObjectName("currentOperator")
        self.status_label = QLabel("未录入操作员" if not session.operator else "操作员已确认")
        self.switch_button = QPushButton("切换")
        self.switch_button.setToolTip("切换操作员会中断当前未完成的扫码作业")
        layout.addWidget(self.prompt_label)
        self.current_label.setWordWrap(True)
        layout.addWidget(self.operator_input)
        layout.addWidget(self.sign_in_button)
        layout.addWidget(self.current_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.switch_button)
        self.sign_in_button.clicked.connect(self._sign_in)
        self.operator_input.returnPressed.connect(self._sign_in)
        self.switch_button.clicked.connect(self._begin_switch)
        self._set_editing(not bool(session.operator))

    @Slot()
    def _sign_in(self) -> None:
        try:
            operator = self._session.sign_in(self.operator_input.text())
        except ValueError as error:
            self.status_label.setStyleSheet("color: #b42318;")
            self.status_label.setText(str(error))
            return
        self.operator_input.setText(operator)
        self.current_label.setText(self._label_text())
        self.status_label.setStyleSheet("color: #18794e;")
        self.status_label.setText("操作员已确认")
        self._announcer.announce(VoicePrompt.OPERATOR_CONFIRMED)
        self.operator_changed.emit(operator)
        self._set_editing(False)

    @Slot()
    def _begin_switch(self) -> None:
        self._set_editing(True)
        self.operator_input.setFocus()
        self.operator_input.selectAll()

    def _set_editing(self, editing: bool) -> None:
        self.prompt_label.setVisible(editing)
        self.operator_input.setVisible(editing)
        self.sign_in_button.setVisible(editing)
        self.status_label.setVisible(editing)
        self.current_label.setVisible(not editing)
        self.switch_button.setVisible(not editing)

    def _label_text(self) -> str:
        return f"当前操作员：{self._session.operator or '-'}"
