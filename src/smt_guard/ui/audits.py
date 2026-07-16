"""Read-only audit log query page."""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from smt_guard.audit import AuditEntry
from smt_guard.ui.components import (
    EmptyState,
    PageHeader,
    content_card,
    prepare_table,
    section_heading,
    set_feedback,
)
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
    ENTITY_NAMES = {
        "DEVICE": "设备",
        "STATION": "站位",
        "BOM": "BOM",
        "PRODUCT_CONFIGURATION": "产品配置",
        "PRODUCTION_RUN": "生产运行",
    }
    ACTION_NAMES = {
        "CREATE": "创建",
        "UPDATE": "修改",
        "ENABLE": "启用",
        "DISABLE": "停用",
        "IMPORT": "导入",
        "PUBLISH": "发布",
        "ACTIVATE": "启用",
        "INTERRUPT": "中断",
        "START": "开始",
        "COMPLETE": "完成",
    }

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
        self._entries: list[AuditEntry] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(
            PageHeader(
                "审计日志",
                "按业务对象、操作员和时间追溯关键变更；日志只读且不可删除。",
            )
        )
        filter_card = content_card(object_name="filterCard")
        filter_layout = QVBoxLayout(filter_card)
        filter_layout.addWidget(section_heading("筛选条件", "默认加载最近 7 天的最新记录"))
        filters = QHBoxLayout()
        self.entity_type_input = QLineEdit()
        self.entity_type_input.setPlaceholderText("业务对象，例如设备或生产运行")
        self.entity_key_input = QLineEdit()
        self.entity_key_input.setPlaceholderText("编号或关键字")
        self.actor_input = QLineEdit()
        self.actor_input.setPlaceholderText("操作员")
        self.action_input = QLineEdit()
        self.action_input.setPlaceholderText("动作，例如启用或中断")
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
        filter_layout.addLayout(filters)
        self.date_range = DateRangeFilter(clock=self._clock, default_days=7)
        self.started_from_input = self.date_range.started_from_input
        self.started_to_input = self.date_range.started_to_input
        filter_layout.addWidget(self.date_range)
        layout.addWidget(filter_card)

        result_header = QHBoxLayout()
        result_header.addWidget(section_heading("查询结果", "选择一行查看完整变更内容"), 1)
        self.result_count_chip = QLabel("0 条")
        self.result_count_chip.setProperty("metricChip", True)
        self.result_count_chip.setProperty("metricTone", "primary")
        result_header.addWidget(self.result_count_chip)
        layout.addLayout(result_header)

        splitter = QSplitter()
        self.audit_stack = QStackedWidget()
        self.empty_state = EmptyState(
            "等待加载审计日志",
            "打开页面后会自动查询最近记录，也可以修改筛选条件后重新查询。",
        )
        self.audit_stack.addWidget(self.empty_state)
        self.audit_table = QTableWidget(0, len(self.HEADERS))
        self.audit_table.setHorizontalHeaderLabels(self.HEADERS)
        prepare_table(self.audit_table)
        self.audit_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.audit_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        set_column_widths(self.audit_table, (50, 135, 80, 165, 75, 90, 280, 280))
        self.audit_table.setColumnHidden(6, True)
        self.audit_table.setColumnHidden(7, True)
        self.audit_table.horizontalHeader().setStretchLastSection(True)
        self.audit_stack.addWidget(self.audit_table)
        splitter.addWidget(self.audit_stack)

        detail_card = content_card(object_name="detailCard")
        detail_card.setMinimumWidth(310)
        detail_card.setMaximumWidth(400)
        detail_layout = QVBoxLayout(detail_card)
        self.detail_title = QLabel("选择一条日志")
        self.detail_title.setObjectName("sectionTitle")
        self.detail_meta = QLabel("完整的变更前后内容将在这里显示")
        self.detail_meta.setObjectName("sectionDescription")
        self.detail_meta.setWordWrap(True)
        detail_layout.addWidget(self.detail_title)
        detail_layout.addWidget(self.detail_meta)
        detail_layout.addWidget(QLabel("变更前"))
        self.before_text = QPlainTextEdit()
        self.before_text.setReadOnly(True)
        self.before_text.setPlaceholderText("无变更前数据")
        detail_layout.addWidget(self.before_text, 1)
        detail_layout.addWidget(QLabel("变更后"))
        self.after_text = QPlainTextEdit()
        self.after_text.setReadOnly(True)
        self.after_text.setPlaceholderText("无变更后数据")
        detail_layout.addWidget(self.after_text, 1)
        splitter.addWidget(detail_card)
        splitter.setSizes((720, 340))
        layout.addWidget(splitter, 1)
        self.status_label = QLabel("尚未查询；打开本页后将自动加载最新审计日志")
        set_feedback(
            self.status_label,
            "neutral",
            "尚未查询；打开本页后将自动加载最新审计日志",
        )
        layout.addWidget(self.status_label)
        self.query_button.clicked.connect(self.refresh)
        self.entity_key_input.returnPressed.connect(self.refresh)
        self.date_range.range_selected.connect(self.refresh)
        self.audit_table.itemSelectionChanged.connect(self._render_selected)

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
        self._entries = entries
        self.audit_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            values = (
                str(entry.id),
                display_datetime(entry.timestamp),
                self.ENTITY_NAMES.get(entry.entity_type, entry.entity_type),
                entry.entity_key,
                self.ACTION_NAMES.get(entry.action, entry.action),
                entry.actor,
                entry.before_json or "",
                entry.after_json or "",
            )
            for column, value in enumerate(values):
                self.audit_table.setItem(row, column, readable_item(value))
            self.audit_table.item(row, 2).setToolTip(entry.entity_type)  # type: ignore[union-attr]
            self.audit_table.item(row, 4).setToolTip(entry.action)  # type: ignore[union-attr]
        self.result_count_chip.setText(f"{len(entries)} 条")
        if entries:
            self.audit_stack.setCurrentWidget(self.audit_table)
            self.audit_table.selectRow(0)
            self._render_selected()
        else:
            self.empty_state.set_message(
                "没有匹配的审计日志",
                "请扩大日期范围或减少筛选条件后重新查询。",
            )
            self.audit_stack.setCurrentWidget(self.empty_state)
            self._clear_detail()
        set_feedback(
            self.status_label,
            "neutral",
            f"查询完成：{len(entries)} 条审计日志（最新优先）"
            f" · 更新于 {self._clock():%H:%M}",
        )

    @Slot()
    def _render_selected(self) -> None:
        row = self.audit_table.currentRow()
        if not 0 <= row < len(self._entries):
            self._clear_detail()
            return
        entry = self._entries[row]
        entity = self.ENTITY_NAMES.get(entry.entity_type, entry.entity_type)
        action = self.ACTION_NAMES.get(entry.action, entry.action)
        self.detail_title.setText(f"{entity} · {action}")
        self.detail_meta.setText(
            f"{entry.entity_key}\n{display_datetime(entry.timestamp)} · 操作员 {entry.actor}"
        )
        self.before_text.setPlainText(self._pretty_json(entry.before_json))
        self.after_text.setPlainText(self._pretty_json(entry.after_json))

    def _clear_detail(self) -> None:
        self.detail_title.setText("选择一条日志")
        self.detail_meta.setText("完整的变更前后内容将在这里显示")
        self.before_text.clear()
        self.after_text.clear()

    @staticmethod
    def _pretty_json(value: str | None) -> str:
        if not value:
            return ""
        try:
            return json.dumps(json.loads(value), ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            return value

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        """Reload append-only audit data whenever the tab becomes visible."""
        super().showEvent(event)
        self.refresh()
