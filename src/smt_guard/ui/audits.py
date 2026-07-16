"""Read-only audit log query page."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from PySide6.QtCore import Slot
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from smt_guard.audit import AuditEntry
from smt_guard.ui.date_range import DateRangeFilter
from smt_guard.ui.formatting import display_datetime
from smt_guard.ui.tables import readable_item, set_column_widths


class AuditReader(Protocol):
    def search(
        self,
        *,
        entity_type: str = "",
        entity_key: str = "",
        actor: str = "",
        action: str = "",
        started_from: datetime | None = None,
        started_to: datetime | None = None,
        limit: int = 1000,
    ) -> list[AuditEntry]: ...


class AuditLogWidget(QWidget):
    """Filter append-only audits without exposing mutation controls."""

    HEADERS = ("编号", "时间", "实体", "实体键", "动作", "操作员", "变更前", "变更后")

    def __init__(
        self,
        repository: AuditReader,
        parent: QWidget | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        super().__init__(parent)
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(UTC))
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("审计日志查询")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        filters = QHBoxLayout()
        self.entity_type_input = QLineEdit()
        self.entity_type_input.setPlaceholderText("实体类型")
        self.entity_key_input = QLineEdit()
        self.entity_key_input.setPlaceholderText("实体键（包含）")
        self.actor_input = QLineEdit()
        self.actor_input.setPlaceholderText("操作员（包含）")
        self.action_input = QLineEdit()
        self.action_input.setPlaceholderText("动作")
        self.query_button = QPushButton("查询")
        self.query_button.setProperty("actionRole", "primary")
        for widget in (
            self.entity_type_input,
            self.entity_key_input,
            self.actor_input,
            self.action_input,
            self.query_button,
        ):
            filters.addWidget(widget)
        layout.addLayout(filters)
        self.date_range = DateRangeFilter(clock=self._clock, default_days=7)
        self.started_from_input = self.date_range.started_from_input
        self.started_to_input = self.date_range.started_to_input
        layout.addWidget(self.date_range)
        self.audit_table = QTableWidget(0, len(self.HEADERS))
        self.audit_table.setHorizontalHeaderLabels(self.HEADERS)
        self.audit_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.audit_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.audit_table.verticalHeader().setVisible(False)
        set_column_widths(self.audit_table, (70, 190, 120, 240, 110, 120, 280, 280))
        layout.addWidget(self.audit_table, 1)
        self.status_label = QLabel("尚未查询；打开本页后将自动加载最新审计日志")
        layout.addWidget(self.status_label)
        self.query_button.clicked.connect(self.refresh)
        self.entity_key_input.returnPressed.connect(self.refresh)
        self.date_range.range_selected.connect(self.refresh)

    @Slot()
    def refresh(self) -> None:
        started_from, started_to = self.date_range.values()
        entries = self._repository.search(
            entity_type=self.entity_type_input.text(),
            entity_key=self.entity_key_input.text(),
            actor=self.actor_input.text(),
            action=self.action_input.text(),
            started_from=started_from,
            started_to=started_to,
        )
        self.audit_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            values = (
                str(entry.id),
                display_datetime(entry.timestamp),
                entry.entity_type,
                entry.entity_key,
                entry.action,
                entry.actor,
                entry.before_json or "",
                entry.after_json or "",
            )
            for column, value in enumerate(values):
                self.audit_table.setItem(row, column, readable_item(value))
        self.status_label.setStyleSheet("color: #344054;")
        self.status_label.setText(
            f"查询完成：{len(entries)} 条审计日志（最新优先）"
            f" · 更新于 {self._clock():%H:%M}"
        )

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        """Reload append-only audit data whenever the tab becomes visible."""
        super().showEvent(event)
        self.refresh()
