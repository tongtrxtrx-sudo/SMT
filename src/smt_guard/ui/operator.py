"""Application-wide operator sign-in control."""

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget

from smt_guard.operator import OperatorSession


class OperatorSessionWidget(QWidget):
    """Capture the operator used by all subsequent write operations."""

    operator_changed = Signal(str)

    def __init__(self, session: OperatorSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session = session
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.addWidget(QLabel("当前操作员"))
        self.operator_input = QLineEdit(session.operator)
        self.operator_input.setPlaceholderText("请输入工号或姓名")
        self.sign_in_button = QPushButton("确认操作员")
        self.current_label = QLabel(self._label_text())
        self.status_label = QLabel("未录入操作员" if not session.operator else "操作员已确认")
        layout.addWidget(self.operator_input, 1)
        layout.addWidget(self.sign_in_button)
        layout.addWidget(self.current_label)
        layout.addWidget(self.status_label)
        self.sign_in_button.clicked.connect(self._sign_in)
        self.operator_input.returnPressed.connect(self._sign_in)

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
        self.operator_changed.emit(operator)

    def _label_text(self) -> str:
        return f"已登录：{self._session.operator or '-'}"
