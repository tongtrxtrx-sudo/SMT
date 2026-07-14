"""Shared table readability helpers for operator-facing pages."""

from collections.abc import Sequence

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem


def readable_item(value: object) -> QTableWidgetItem:
    """Create a table item whose complete value remains available as a tooltip."""
    text = str(value)
    item = QTableWidgetItem(text)
    item.setToolTip(text)
    return item


def set_column_widths(table: QTableWidget, widths: Sequence[int]) -> None:
    """Apply business-priority default widths while preserving horizontal scrolling."""
    for column, width in enumerate(widths):
        table.setColumnWidth(column, width)
