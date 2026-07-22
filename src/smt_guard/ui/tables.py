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
        self._states, self._extents = self._load()

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
        extent = max(widget.width(), 0)
        if self._states.get(key) == encoded and self._extents.get(key) == extent:
            return
        self._states[key] = encoded
        self._extents[key] = extent
        self._persist()

    def reference_extent(self, key: str) -> int | None:
        """Return the viewport width used when a layout state was saved."""
        return self._extents.get(key)

    def remove(self, key: str) -> None:
        """Remove one saved layout without affecting business data."""
        changed = self._states.pop(key, None) is not None
        changed = self._extents.pop(key, None) is not None or changed
        if changed:
            self._persist()

    def clear(self) -> None:
        """Clear all saved table and splitter layouts."""
        if not self._states and not self._extents:
            return
        self._states.clear()
        self._extents.clear()
        self._persist()

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(f"{self._path.suffix}.tmp")
        payload = {
            "version": 2,
            "states": self._states,
            "extents": self._extents,
        }
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self._path)

    def _load(self) -> tuple[dict[str, str], dict[str, int]]:
        try:
            payload: object = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return {}, {}
            payload_mapping = cast(dict[str, object], payload)
            states = payload_mapping.get("states", {})
            if not isinstance(states, dict):
                return {}, {}
            typed_states = cast(dict[object, object], states)
            loaded_states = {
                str(key): value
                for key, value in typed_states.items()
                if isinstance(value, str)
            }
            extents = payload_mapping.get("extents", {})
            if not isinstance(extents, dict):
                return loaded_states, {}
            typed_extents = cast(dict[object, object], extents)
            loaded_extents = {
                str(key): value
                for key, value in typed_extents.items()
                if isinstance(value, int) and value > 0
            }
            return loaded_states, loaded_extents
        except (OSError, ValueError, TypeError):
            return {}, {}


class _TableLayoutController(QObject):
    def __init__(
        self,
        table: QTableWidget,
        key: str,
        store: UiLayoutStore | None,
        narrow_hidden: Sequence[int],
        narrow_threshold: int,
    ) -> None:
        super().__init__(table)
        self._table = table
        self._key = f"table/{key}/columns-{table.columnCount()}"
        self._store = store
        self._narrow_hidden = frozenset(narrow_hidden)
        self._narrow_threshold = narrow_threshold
        self._base_hidden = [
            table.isColumnHidden(column) for column in range(table.columnCount())
        ]
        self._default_widths: list[int] = []
        self._minimum_widths: list[int] = []
        self._stretch_columns: frozenset[int] = frozenset()
        self._narrow = False
        self._applying_layout = False
        self._initialized = False
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(250)
        self._save_timer.timeout.connect(self._save)
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._adapt_to_viewport)
        table.installEventFilter(self)
        header = table.horizontalHeader()
        header.setSectionsMovable(True)
        header.setFirstSectionMovable(True)
        header.setMinimumSectionSize(48)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table.clicked.connect(self._show_truncated_value)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        table = getattr(self, "_table", None)
        if watched is table:
            if event.type() == QEvent.Type.Show:
                self._initialize()
            elif event.type() == QEvent.Type.Resize and self._initialized:
                self._resize_timer.start(0)
        return super().eventFilter(watched, event)

    def _initialize(self) -> None:
        if self._initialized or self._table.columnCount() == 0:
            return
        self._initialized = True
        header = self._table.horizontalHeader()
        self._stretch_columns = frozenset(
            column
            for column in range(self._table.columnCount())
            if header.sectionResizeMode(column) == QHeaderView.ResizeMode.Stretch
        )
        configured_widths = getattr(self._table, "_ui_default_column_widths", ())
        self._default_widths = (
            list(configured_widths)
            if len(configured_widths) == self._table.columnCount()
            else [
                header.sectionSize(column)
                for column in range(self._table.columnCount())
            ]
        )
        configured_minimums = getattr(self._table, "_ui_minimum_column_widths", ())
        self._minimum_widths = (
            list(configured_minimums)
            if len(configured_minimums) == self._table.columnCount()
            else [header.minimumSectionSize()] * self._table.columnCount()
        )
        for column in range(self._table.columnCount()):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
        reference_extent = (
            self._store.reference_extent(self._key) if self._store else None
        )
        restored = self._store.restore(self._key, header) if self._store else False
        self._apply_narrow_visibility(force=True)
        if restored:
            scale = (
                header.width() / reference_extent
                if reference_extent is not None
                and _extent_changed(reference_extent, header.width())
                else 1.0
            )
            restored_widths = [
                max(round(header.sectionSize(column) * scale), header.minimumSectionSize())
                for column in range(self._table.columnCount())
            ]
            # A saved layout can contain widths whose total is smaller than the
            # current viewport (for example after columns were hidden). Always
            # fit the restored widths so visible columns do not leave a blank band.
            self._fit_widths(restored_widths)
        else:
            self._fit_default_widths()
        header.sectionMoved.connect(self._queue_save)
        header.sectionResized.connect(self._queue_save)

    def _adapt_to_viewport(self) -> None:
        if not self._initialized:
            return
        previous_narrow = self._narrow
        self._apply_narrow_visibility()
        if previous_narrow != self._narrow:
            self._fit_default_widths()
            return
        header = self._table.horizontalHeader()
        self._fit_widths(
            [
                header.sectionSize(column)
                for column in range(self._table.columnCount())
            ]
        )

    def _apply_narrow_visibility(self, *, force: bool = False) -> None:
        self._narrow = bool(
            self._narrow_threshold
            and self._table.viewport().width() < self._narrow_threshold
        )
        for column, base_hidden in enumerate(self._base_hidden):
            hidden = base_hidden or (self._narrow and column in self._narrow_hidden)
            if force and hidden and self._table.isColumnHidden(column):
                # Restoring a state saved while narrow can leave Qt's hidden
                # section offset behind. Re-toggling collapses that stale gap.
                self._table.setColumnHidden(column, False)
            self._table.setColumnHidden(column, hidden)

    def set_column_hidden(self, column: int, hidden: bool) -> None:
        """Update a business-controlled column without losing it on resize/restore."""
        if not 0 <= column < len(self._base_hidden):
            raise IndexError(f"table column out of range: {column}")
        self._base_hidden[column] = hidden
        self._apply_narrow_visibility(force=hidden)
        if self._initialized:
            self._fit_default_widths()

    def _fit_default_widths(self) -> None:
        self._fit_widths(self._default_widths)

    def _fit_widths(self, source_widths: Sequence[int]) -> None:
        if not source_widths:
            return
        header = self._table.horizontalHeader()
        visible = [
            column
            for column in range(self._table.columnCount())
            if not self._table.isColumnHidden(column)
        ]
        if not visible:
            return
        widths = {
            column: max(source_widths[column], self._minimum_widths[column])
            for column in visible
        }
        required = sum(self._minimum_widths[column] for column in visible)
        available = max(self._table.viewport().width() - 4, required)
        total = sum(widths.values())
        if total > available:
            overflow = total - available
            stretch_first: list[int] = sorted(
                [column for column in visible if column in self._stretch_columns],
                key=lambda column: widths[column],
                reverse=True,
            )
            fixed_after: list[int] = sorted(
                [column for column in visible if column not in self._stretch_columns],
                key=lambda column: widths[column],
                reverse=True,
            )
            for column in (*stretch_first, *fixed_after):
                reducible = max(widths[column] - self._minimum_widths[column], 0)
                reduction = min(reducible, overflow)
                widths[column] -= reduction
                overflow -= reduction
                if overflow <= 0:
                    break
        elif total < available:
            stretch = [column for column in visible if column in self._stretch_columns]
            if stretch:
                spare = available - total
                per_column, remainder = divmod(spare, len(stretch))
                for index, column in enumerate(stretch):
                    widths[column] += per_column + (1 if index < remainder else 0)
        self._applying_layout = True
        try:
            for column, width in widths.items():
                header.resizeSection(column, width)
        finally:
            self._applying_layout = False

    def _queue_save(self, *_args: object) -> None:
        if self._store is not None and not self._applying_layout:
            self._save_timer.start()

    def reset(self) -> None:
        if self._store is not None:
            self._store.remove(self._key)
        header = self._table.horizontalHeader()
        self._applying_layout = True
        try:
            for logical_index in range(self._table.columnCount()):
                visual_index = header.visualIndex(logical_index)
                if visual_index != logical_index:
                    header.moveSection(visual_index, logical_index)
            self._apply_narrow_visibility()
            self._fit_default_widths()
        finally:
            self._applying_layout = False

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
        narrow_ratios: Sequence[int],
        narrow_threshold: int,
    ) -> None:
        super().__init__(splitter)
        self._splitter = splitter
        self._key = f"splitter/{key}/panes-{splitter.count()}"
        self._store = store
        self._narrow_ratios = tuple(narrow_ratios)
        self._narrow_threshold = narrow_threshold
        self._default_ratios: tuple[int, ...] = ()
        self._narrow = False
        self._applying_layout = False
        self._initialized = False
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(250)
        self._save_timer.timeout.connect(self._save)
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._adapt_to_viewport)
        splitter.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        splitter = getattr(self, "_splitter", None)
        if watched is splitter:
            if event.type() == QEvent.Type.Show:
                self._initialize()
            elif event.type() == QEvent.Type.Resize and self._initialized:
                self._resize_timer.start(0)
        return super().eventFilter(watched, event)

    def _initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._default_ratios = tuple(max(size, 1) for size in self._splitter.sizes())
        reference_extent = (
            self._store.reference_extent(self._key) if self._store else None
        )
        restored = self._store.restore(self._key, self._splitter) if self._store else False
        restored_ratios = tuple(max(size, 1) for size in self._splitter.sizes())
        self._narrow = self._is_narrow()
        if restored and (
            reference_extent is None
            or _extent_changed(reference_extent, self._splitter.width())
        ):
            self._apply_ratios(restored_ratios)
        elif not restored:
            self._apply_default_ratios()
        self._splitter.splitterMoved.connect(self._queue_save)

    def _is_narrow(self) -> bool:
        return bool(
            self._narrow_ratios
            and self._narrow_threshold
            and self._splitter.width() < self._narrow_threshold
        )

    def _apply_default_ratios(self) -> None:
        ratios = self._narrow_ratios if self._is_narrow() else self._default_ratios
        self._apply_ratios(ratios)

    def _apply_ratios(self, ratios: Sequence[int]) -> None:
        if len(ratios) != self._splitter.count() or not any(ratios):
            return
        available = max(
            self._splitter.width()
            - self._splitter.handleWidth() * max(self._splitter.count() - 1, 0),
            self._splitter.count(),
        )
        ratio_total = sum(ratios)
        sizes = [max(round(available * ratio / ratio_total), 1) for ratio in ratios]
        self._applying_layout = True
        try:
            self._splitter.setSizes(sizes)
        finally:
            self._applying_layout = False

    def _adapt_to_viewport(self) -> None:
        narrow = self._is_narrow()
        if narrow == self._narrow:
            return
        self._narrow = narrow
        self._apply_default_ratios()

    def _queue_save(self, *_args: object) -> None:
        if self._store is not None and not self._applying_layout:
            self._save_timer.start()

    def reset(self) -> None:
        if self._store is not None:
            self._store.remove(self._key)
        self._apply_default_ratios()

    def _save(self) -> None:
        if self._store is not None:
            self._store.save(self._key, self._splitter)


def enable_table_layout(
    table: QTableWidget,
    key: str,
    store: UiLayoutStore | None,
    *,
    narrow_hidden: Sequence[int] = (),
    narrow_threshold: int = 0,
) -> None:
    """Allow column resizing/reordering and restore the previous arrangement."""
    table._ui_layout_controller = _TableLayoutController(  # type: ignore[attr-defined]
        table,
        key,
        store,
        narrow_hidden,
        narrow_threshold,
    )


def enable_splitter_layout(
    splitter: QSplitter,
    key: str,
    store: UiLayoutStore | None,
    *,
    narrow_ratios: Sequence[int] = (),
    narrow_threshold: int = 0,
) -> None:
    """Restore and save a user-adjustable split pane."""
    splitter._ui_layout_controller = _SplitterLayoutController(  # type: ignore[attr-defined]
        splitter,
        key,
        store,
        narrow_ratios,
        narrow_threshold,
    )


def set_managed_column_hidden(
    table: QTableWidget,
    column: int,
    hidden: bool,
) -> None:
    """Keep a programmatically hidden column stable across layout restoration."""
    controller = getattr(table, "_ui_layout_controller", None)
    if isinstance(controller, _TableLayoutController):
        controller.set_column_hidden(column, hidden)
        return
    table.setColumnHidden(column, hidden)


def reset_persistent_layouts(root: QObject, store: UiLayoutStore | None) -> None:
    """Reset every managed table and splitter below ``root`` immediately."""
    if store is not None:
        store.clear()
    for table in root.findChildren(QTableWidget):
        controller = getattr(table, "_ui_layout_controller", None)
        if isinstance(controller, _TableLayoutController):
            controller.reset()
    for splitter in root.findChildren(QSplitter):
        controller = getattr(splitter, "_ui_layout_controller", None)
        if isinstance(controller, _SplitterLayoutController):
            controller.reset()


def _extent_changed(saved: int, current: int) -> bool:
    if saved <= 0 or current <= 0:
        return True
    return abs(current - saved) / saved > 0.15


def readable_item(value: object) -> QTableWidgetItem:
    """Create a table item whose complete value remains available as a tooltip."""
    text = str(value)
    item = QTableWidgetItem(text)
    item.setToolTip(text)
    return item


def set_column_widths(table: QTableWidget, widths: Sequence[int]) -> None:
    """Apply business-priority default widths while preserving horizontal scrolling."""
    table._ui_default_column_widths = tuple(widths)  # type: ignore[attr-defined]
    for column, width in enumerate(widths):
        table.setColumnWidth(column, width)


def set_column_minimum_widths(table: QTableWidget, widths: Sequence[int]) -> None:
    """Keep critical columns readable even when restoring an older saved layout."""
    if len(widths) != table.columnCount():
        raise ValueError("minimum width count must match table column count")
    table._ui_minimum_column_widths = tuple(widths)  # type: ignore[attr-defined]


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
