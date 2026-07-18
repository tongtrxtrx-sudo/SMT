"""Shared table readability helpers for operator-facing pages."""

from collections.abc import Sequence

from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem


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


def set_responsive_columns(
    table: QTableWidget,
    *,
    stretch: Sequence[int],
    compact: Sequence[int] = (),
) -> None:
    """Let important columns share spare full-screen width without one giant last column."""
    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    stretch_columns = set(stretch)
    compact_columns = set(compact)
    for column in range(table.columnCount()):
        if column in compact_columns:
            mode = QHeaderView.ResizeMode.ResizeToContents
        elif column in stretch_columns:
            mode = QHeaderView.ResizeMode.Stretch
        else:
            mode = QHeaderView.ResizeMode.Interactive
        header.setSectionResizeMode(column, mode)
