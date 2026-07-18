"""Shared table readability and persistent layout helpers."""

import html
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import QByteArray, QEvent, QModelIndex, QObject, Qt, QTimer
from PySide6.QtWidgets import (
    QHeaderView,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolTip,
)


class UiLayoutStore:
    """Persist table headers and split panes beside the application database."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._states = self._load()

    def restore(self, key: str, widget: QHeaderView | QSplitter) -> bool:
        encoded = self._states.get(key)
        if not encoded:
            return False
        try:
            state = QByteArray.fromBase64(encoded.encode("ascii"))
            return widget.restoreState(state)
        except (TypeError, ValueError):
            return False

    def save(self, key: str, widget: QHeaderView | QSplitter) -> None:
        base64_state = cast(Any, widget.saveState().toBase64())
        encoded = bytes(base64_state).decode("ascii")
        if self._states.get(key) == encoded:
            return
        self._states[key] = encoded
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(f"{self._path.suffix}.tmp")
        payload = {"version": 1, "states": self._states}
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self._path)

    def _load(self) -> dict[str, str]:
        try:
            payload: object = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return {}
            payload_mapping = cast(dict[str, object], payload)
            states = payload_mapping.get("states", {})
            if not isinstance(states, dict):
                return {}
            typed_states = cast(dict[object, object], states)
            return {
                str(key): value
                for key, value in typed_states.items()
                if isinstance(value, str)
            }
        except (OSError, ValueError, TypeError):
            return {}


class _TableLayoutController(QObject):
    def __init__(
        self,
        table: QTableWidget,
        key: str,
        store: UiLayoutStore | None,
    ) -> None:
        super().__init__(table)
        self._table = table
        self._key = f"table/{key}/columns-{table.columnCount()}"
        self._store = store
        self._initialized = False
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(250)
        self._save_timer.timeout.connect(self._save)
        table.installEventFilter(self)
        header = table.horizontalHeader()
        header.setSectionsMovable(True)
        header.setFirstSectionMovable(True)
        header.setMinimumSectionSize(48)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table.clicked.connect(self._show_truncated_value)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        table = getattr(self, "_table", None)
        if watched is table and event.type() == QEvent.Type.Show:
            self._initialize()
        return super().eventFilter(watched, event)

    def _initialize(self) -> None:
        if self._initialized or self._table.columnCount() == 0:
            return
        self._initialized = True
        header = self._table.horizontalHeader()
        calculated_widths = [
            header.sectionSize(column)
            for column in range(self._table.columnCount())
        ]
        for column in range(self._table.columnCount()):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
        restored = self._store.restore(self._key, header) if self._store else False
        if not restored:
            visible_columns = [
                column
                for column in range(self._table.columnCount())
                if not self._table.isColumnHidden(column)
            ]
            overflow = max(
                sum(calculated_widths[column] for column in visible_columns)
                - max(self._table.viewport().width() - 4, 0),
                0,
            )
            for column in reversed(visible_columns):
                reducible = max(
                    calculated_widths[column] - header.minimumSectionSize(),
                    0,
                )
                reduction = min(reducible, overflow)
                calculated_widths[column] -= reduction
                overflow -= reduction
                if overflow == 0:
                    break
            for column, width in enumerate(calculated_widths):
                header.resizeSection(column, width)
        header.sectionMoved.connect(self._queue_save)
        header.sectionResized.connect(self._queue_save)

    def _queue_save(self, *_args: object) -> None:
        if self._store is not None:
            self._save_timer.start()

    def _save(self) -> None:
        if self._store is not None:
            self._store.save(self._key, self._table.horizontalHeader())

    def _show_truncated_value(self, index: QModelIndex) -> None:
        """Show the complete cell value when the visible column truncates it."""
        if not index.isValid():
            return
        value = index.data(Qt.ItemDataRole.DisplayRole)
        if value is None:
            return
        text = str(value)
        cell_rect = self._table.visualRect(index)
        available_width = max(cell_rect.width() - 16, 0)
        if (
            "\n" not in text
            and self._table.fontMetrics().horizontalAdvance(text) <= available_width
        ):
            QToolTip.hideText()
            return
        rich_text = (
            '<div style="max-width: 640px; white-space: pre-wrap;">'
            f"{html.escape(text).replace(chr(10), '<br>')}"
            "</div>"
        )
        viewport = self._table.viewport()
        position = viewport.mapToGlobal(cell_rect.bottomLeft())
        QToolTip.showText(position, rich_text, viewport, cell_rect, 12000)


class _SplitterLayoutController(QObject):
    def __init__(
        self,
        splitter: QSplitter,
        key: str,
        store: UiLayoutStore | None,
    ) -> None:
        super().__init__(splitter)
        self._splitter = splitter
        self._key = f"splitter/{key}/panes-{splitter.count()}"
        self._store = store
        self._initialized = False
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(250)
        self._save_timer.timeout.connect(self._save)
        splitter.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        splitter = getattr(self, "_splitter", None)
        if watched is splitter and event.type() == QEvent.Type.Show:
            self._initialize()
        return super().eventFilter(watched, event)

    def _initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        if self._store is not None:
            self._store.restore(self._key, self._splitter)
        self._splitter.splitterMoved.connect(self._queue_save)

    def _queue_save(self, *_args: object) -> None:
        if self._store is not None:
            self._save_timer.start()

    def _save(self) -> None:
        if self._store is not None:
            self._store.save(self._key, self._splitter)


def enable_table_layout(
    table: QTableWidget,
    key: str,
    store: UiLayoutStore | None,
) -> None:
    """Allow column resizing/reordering and restore the previous arrangement."""
    table._ui_layout_controller = _TableLayoutController(  # type: ignore[attr-defined]
        table,
        key,
        store,
    )


def enable_splitter_layout(
    splitter: QSplitter,
    key: str,
    store: UiLayoutStore | None,
) -> None:
    """Restore and save a user-adjustable split pane."""
    splitter._ui_layout_controller = _SplitterLayoutController(  # type: ignore[attr-defined]
        splitter,
        key,
        store,
    )


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
