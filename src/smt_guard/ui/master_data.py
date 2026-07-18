"""Device and station management widget."""

from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from smt_guard.master_data import Device, MasterDataError, Station
from smt_guard.ui.components import (
    PageHeader,
    content_card,
    prepare_table,
    section_heading,
    set_feedback,
)
from smt_guard.ui.tables import (
    UiLayoutStore,
    enable_splitter_layout,
    enable_table_layout,
    set_column_widths,
    set_responsive_columns,
)


class MasterDataRepository(Protocol):
    """Operations required by the device and station screen."""

    def add_device(
        self, code: str, name: str, line: str, *, actor: str = "SYSTEM"
    ) -> Device:
        """Create one device."""
        ...

    def update_device(
        self, code: str, *, name: str, line: str, actor: str = "SYSTEM"
    ) -> Device: ...

    def enable_device(self, code: str, *, actor: str = "SYSTEM") -> None: ...

    def disable_device(self, code: str, *, actor: str = "SYSTEM") -> None:
        """Disable one device."""
        ...

    def list_devices(self) -> list[Device]:
        """List devices in display order."""
        ...

    def search_devices(
        self, query: str = "", *, enabled: bool | None = None, include_archived: bool = False
    ) -> list[Device]: ...

    def archive_device(self, code: str, *, actor: str = "SYSTEM") -> None: ...

    def delete_device(self, code: str, *, actor: str = "SYSTEM") -> None: ...

    def add_station(
        self,
        device_code: str,
        station_code: str,
        *,
        name: str = "",
        actor: str = "SYSTEM",
    ) -> Station:
        """Create one station."""
        ...

    def bulk_add_stations(
        self,
        device_code: str,
        prefix: str,
        start: int,
        end: int,
        *,
        width: int,
        actor: str = "SYSTEM",
    ) -> list[Station]:
        """Create a formatted station range."""
        ...

    def list_stations(self, device_code: str) -> list[Station]:
        """List stations for one device."""
        ...

    def search_stations(
        self,
        device_code: str,
        query: str = "",
        *,
        enabled: bool | None = None,
        include_archived: bool = False,
    ) -> list[Station]: ...

    def update_station(
        self,
        device_code: str,
        station_code: str,
        *,
        name: str,
        actor: str = "SYSTEM",
    ) -> Station: ...

    def enable_station(
        self, device_code: str, station_code: str, *, actor: str = "SYSTEM"
    ) -> None: ...

    def disable_station(
        self, device_code: str, station_code: str, *, actor: str = "SYSTEM"
    ) -> None:
        """Disable one station."""
        ...

    def archive_station(
        self, device_code: str, station_code: str, *, actor: str = "SYSTEM"
    ) -> None: ...

    def delete_station(
        self, device_code: str, station_code: str, *, actor: str = "SYSTEM"
    ) -> None:
        """Delete one unreferenced station."""
        ...


class LargeStepSpinBox(QSpinBox):
    """Numeric input with explicit shop-floor-sized decrement/increment buttons."""

    BUTTON_WIDTH = 38

    def __init__(self, *, minimum_digits: int = 1) -> None:
        self._minimum_digits = max(1, minimum_digits)
        super().__init__()
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        self.decrement_button = QToolButton(self)
        self.decrement_button.setObjectName("spinDecrement")
        self.decrement_button.setText("−")
        self.decrement_button.setToolTip("减少 1")
        self.decrement_button.setAccessibleName("减少 1")

        self.increment_button = QToolButton(self)
        self.increment_button.setObjectName("spinIncrement")
        self.increment_button.setText("+")
        self.increment_button.setToolTip("增加 1")
        self.increment_button.setAccessibleName("增加 1")

        for button in (self.decrement_button, self.increment_button):
            button.setAutoRepeat(True)
            button.setAutoRepeatDelay(350)
            button.setAutoRepeatInterval(90)

        self.decrement_button.clicked.connect(self.stepDown)
        self.increment_button.clicked.connect(self.stepUp)

    def textFromValue(self, value: int) -> str:  # noqa: N802
        """Keep configured leading zeroes without changing the numeric value."""
        return str(value).zfill(self._minimum_digits)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Keep both buttons large and aligned at the right edge."""
        super().resizeEvent(event)
        button_height = max(self.height() - 4, 1)
        increment_left = self.width() - self.BUTTON_WIDTH - 2
        decrement_left = increment_left - self.BUTTON_WIDTH - 2
        self.decrement_button.setGeometry(
            decrement_left,
            2,
            self.BUTTON_WIDTH,
            button_height,
        )
        self.increment_button.setGeometry(
            increment_left,
            2,
            self.BUTTON_WIDTH,
            button_height,
        )
        self.decrement_button.raise_()
        self.increment_button.raise_()


class DeviceStationWidget(QWidget):
    """Manage placement devices and their physical feeder stations."""

    master_data_changed = Signal()

    def __init__(
        self,
        repository: MasterDataRepository,
        *,
        operator_provider: Callable[[], str] | None = None,
        layout_store: UiLayoutStore | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._repository = repository
        self._operator_provider = operator_provider
        self._layout_store = layout_store
        self._build_ui()
        self._connect_signals()
        self.refresh_devices()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.addWidget(
            PageHeader(
                "设备与站位",
                "先选择设备，再维护该设备的站位；批量创建等低频操作默认收起。",
            )
        )

        splitter = QSplitter()
        self.splitter = splitter
        splitter.addWidget(self._build_device_panel())
        splitter.addWidget(self._build_station_panel())
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([900, 900])
        enable_splitter_layout(splitter, "master-data/main", self._layout_store)
        root.addWidget(splitter, 1)

        self.status_label = QLabel("就绪")
        self.status_label.setObjectName("feedbackLabel")
        set_feedback(self.status_label, "neutral", "就绪")
        root.addWidget(self.status_label)

    def _build_device_panel(self) -> QWidget:
        panel = content_card()
        layout = QVBoxLayout(panel)
        heading = QHBoxLayout()
        heading.addWidget(section_heading("设备", "选择后可编辑名称、产线和状态"), 1)
        self.device_count_label = QLabel("0 台")
        self.device_count_label.setProperty("metricChip", True)
        self.device_count_label.setProperty("metricTone", "primary")
        heading.addWidget(self.device_count_label)
        layout.addLayout(heading)
        query = QHBoxLayout()
        self.device_query_input = QLineEdit()
        self.device_query_input.setPlaceholderText("按编码、名称或产线筛选")
        self.device_status_filter = QComboBox()
        self.device_status_filter.addItems(("全部状态", "启用", "停用"))
        query.addWidget(self.device_query_input, 1)
        query.addWidget(self.device_status_filter)
        layout.addLayout(query)

        self.device_table = self._table(("设备编码", "设备名称", "产线", "状态"))
        set_column_widths(self.device_table, (105, 150, 105, 70))
        set_responsive_columns(
            self.device_table,
            stretch=(0, 1, 2),
            compact=(3,),
        )
        enable_table_layout(
            self.device_table,
            "master-data/devices",
            self._layout_store,
        )
        layout.addWidget(self.device_table, 1)

        layout.addWidget(section_heading("设备信息", "修改现有设备，或输入新编码创建设备"))
        form = QFormLayout()
        self.device_code_input = QLineEdit()
        self.device_name_input = QLineEdit()
        self.device_line_input = QLineEdit()
        form.addRow("设备编码", self.device_code_input)
        form.addRow("设备名称", self.device_name_input)
        form.addRow("所属产线", self.device_line_input)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        self.add_device_button = QPushButton("创建设备")
        self.add_device_button.setProperty("actionRole", "primary")
        self.update_device_button = QPushButton("保存修改")
        self.update_device_button.setProperty("actionRole", "primary")
        self.enable_device_button = QPushButton("启用")
        self.enable_device_button.setProperty("actionRole", "success")
        self.disable_device_button = QPushButton("停用")
        self.disable_device_button.setProperty("actionRole", "danger")
        buttons.addWidget(self.add_device_button)
        buttons.addWidget(self.update_device_button)
        buttons.addWidget(self.enable_device_button)
        buttons.addWidget(self.disable_device_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        return panel

    def _build_station_panel(self) -> QWidget:
        panel = content_card()
        layout = QVBoxLayout(panel)
        heading = QHBoxLayout()
        self.selected_device_label = QLabel("站位 · 尚未选择设备")
        self.selected_device_label.setObjectName("sectionTitle")
        heading.addWidget(self.selected_device_label)
        heading.addStretch(1)
        self.station_count_label = QLabel("0 个")
        self.station_count_label.setProperty("metricChip", True)
        heading.addWidget(self.station_count_label)
        layout.addLayout(heading)

        query = QHBoxLayout()
        self.station_query_input = QLineEdit()
        self.station_query_input.setPlaceholderText("按站位编码或名称筛选")
        self.station_status_filter = QComboBox()
        self.station_status_filter.addItems(("全部状态", "启用", "停用"))
        query.addWidget(self.station_query_input, 1)
        query.addWidget(self.station_status_filter)
        layout.addLayout(query)

        self.station_table = self._table(("站位编码", "站位名称", "状态", "已引用"))
        set_column_widths(self.station_table, (110, 170, 70, 70))
        set_responsive_columns(
            self.station_table,
            stretch=(0, 1),
            compact=(2, 3),
        )
        enable_table_layout(
            self.station_table,
            "master-data/stations",
            self._layout_store,
        )
        layout.addWidget(self.station_table, 1)

        layout.addWidget(section_heading("站位信息", "新增或修改当前设备下的单个站位"))
        single_form = QFormLayout()
        self.station_code_input = QLineEdit()
        self.station_name_input = QLineEdit()
        self.add_station_button = QPushButton("新增站位")
        self.add_station_button.setProperty("actionRole", "primary")
        single_form.addRow("站位编码", self.station_code_input)
        single_form.addRow("站位名称", self.station_name_input)
        layout.addLayout(single_form)

        station_buttons = QHBoxLayout()
        self.update_station_button = QPushButton("保存修改")
        self.update_station_button.setProperty("actionRole", "primary")
        self.enable_station_button = QPushButton("启用")
        self.enable_station_button.setProperty("actionRole", "success")
        self.disable_station_button = QPushButton("停用")
        self.disable_station_button.setProperty("actionRole", "danger")
        station_buttons.addWidget(self.add_station_button)
        station_buttons.addWidget(self.update_station_button)
        station_buttons.addWidget(self.enable_station_button)
        station_buttons.addWidget(self.disable_station_button)
        station_buttons.addStretch(1)
        layout.addLayout(station_buttons)

        self.bulk_toggle_button = QPushButton("展开批量创建站位")
        self.bulk_toggle_button.setCheckable(True)
        self.bulk_toggle_button.setProperty("actionRole", "secondary")
        layout.addWidget(self.bulk_toggle_button)
        self.bulk_group = QGroupBox("批量创建站位")
        self.bulk_group.setVisible(False)
        bulk_form = QFormLayout(self.bulk_group)
        self.bulk_prefix_input = QLineEdit("F-")
        self.bulk_start_input = self._spin_box(1, 9999, 1, minimum_digits=2)
        self.bulk_end_input = self._spin_box(1, 9999, 60)
        self.bulk_width_input = self._spin_box(1, 6, 2)
        self.bulk_add_button = QPushButton("批量创建")
        self.bulk_add_button.setProperty("actionRole", "primary")
        bulk_form.addRow("前缀", self.bulk_prefix_input)
        bulk_form.addRow("起始编号", self.bulk_start_input)
        bulk_form.addRow("结束编号", self.bulk_end_input)
        bulk_form.addRow("数字宽度", self.bulk_width_input)
        bulk_form.addRow("", self.bulk_add_button)
        layout.addWidget(self.bulk_group)
        return panel

    def _connect_signals(self) -> None:
        self.add_device_button.clicked.connect(self._add_device)
        self.update_device_button.clicked.connect(self._update_device)
        self.enable_device_button.clicked.connect(self._enable_device)
        self.disable_device_button.clicked.connect(self._disable_device)
        self.device_query_input.textChanged.connect(self._device_filter_changed)
        self.device_status_filter.currentIndexChanged.connect(self._device_filter_changed)
        self.device_table.itemSelectionChanged.connect(self._device_selection_changed)
        self.add_station_button.clicked.connect(self._add_station)
        self.update_station_button.clicked.connect(self._update_station)
        self.enable_station_button.clicked.connect(self._enable_station)
        self.bulk_add_button.clicked.connect(self._bulk_add_stations)
        self.bulk_toggle_button.toggled.connect(self._toggle_bulk_panel)
        self.disable_station_button.clicked.connect(self._disable_station)
        self.station_query_input.textChanged.connect(self._station_filter_changed)
        self.station_status_filter.currentIndexChanged.connect(self._station_filter_changed)
        self.station_table.itemSelectionChanged.connect(self._station_selection_changed)

    @Slot(str)
    @Slot(int)
    @Slot(bool)
    def _device_filter_changed(self, _value: object) -> None:
        self.refresh_devices()

    @Slot(str)
    @Slot(int)
    @Slot(bool)
    def _station_filter_changed(self, _value: object) -> None:
        self._refresh_stations()

    @Slot()
    def refresh_devices(self, preferred_code: str | None = None) -> None:
        selected = preferred_code or self._current_device_code()
        devices = self._repository.search_devices(
            self.device_query_input.text(),
            enabled=self._status_filter(self.device_status_filter),
            include_archived=True,
        )
        self.device_table.blockSignals(True)
        self.device_table.setRowCount(len(devices))
        for row, device in enumerate(devices):
            self._set_row(
                self.device_table,
                row,
                (
                    device.code,
                    device.name,
                    device.line,
                    self._enabled_text(device.enabled and not device.archived),
                ),
            )
        self.device_table.blockSignals(False)
        self.device_count_label.setText(f"{len(devices)} 台")

        target_row = next(
            (row for row, device in enumerate(devices) if device.code == selected),
            0 if devices else -1,
        )
        if target_row >= 0:
            self.device_table.selectRow(target_row)
        else:
            self.device_table.clearSelection()
            self._refresh_stations()
        self._sync_device_state_buttons()

    @Slot()
    def _device_selection_changed(self) -> None:
        row = self.device_table.currentRow()
        if row >= 0:
            for target, column in (
                (self.device_code_input, 0),
                (self.device_name_input, 1),
                (self.device_line_input, 2),
            ):
                item = self.device_table.item(row, column)
                target.setText("" if item is None else item.text())
        self._sync_device_state_buttons()
        self._refresh_stations()

    @Slot()
    def _station_selection_changed(self) -> None:
        row = self.station_table.currentRow()
        if row < 0:
            self._sync_station_state_buttons()
            return
        code = self.station_table.item(row, 0)
        name = self.station_table.item(row, 1)
        self.station_code_input.setText("" if code is None else code.text())
        self.station_name_input.setText("" if name is None else name.text())
        self._sync_station_state_buttons()

    @Slot()
    def _add_device(self) -> None:
        try:
            code = self._required(self.device_code_input.text(), "设备编码")
            name = self._required(self.device_name_input.text(), "设备名称")
            device = self._repository.add_device(
                code, name, self.device_line_input.text(), **self._actor_kwargs()
            )
        except (MasterDataError, ValueError) as error:
            self._show_error(str(error))
            return

        self.device_code_input.clear()
        self.device_name_input.clear()
        self.device_line_input.clear()
        self.refresh_devices(device.code)
        self._show_success(f"已创建设备 {device.code}")

    @Slot()
    def _disable_device(self) -> None:
        device = self._require_selected_device()
        if device is None:
            return
        try:
            self._repository.disable_device(device, **self._actor_kwargs())
        except MasterDataError as error:
            self._show_error(str(error))
            return
        self.refresh_devices(device)
        self._show_success(f"已停用设备 {device}")

    @Slot()
    def _update_device(self) -> None:
        code = self._require_selected_device()
        if code is None:
            return
        try:
            actor_kwargs = self._actor_kwargs()
            was_disabled = self.enable_device_button.isEnabled()
            self._repository.update_device(
                code,
                name=self._required(self.device_name_input.text(), "设备名称"),
                line=self.device_line_input.text(),
                **actor_kwargs,
            )
            if was_disabled:
                self._repository.enable_device(code, **actor_kwargs)
        except (MasterDataError, ValueError) as error:
            self._show_error(str(error))
            return
        self.refresh_devices(code)
        self._show_success(f"已更新并启用设备 {code}")

    @Slot()
    def _enable_device(self) -> None:
        self._device_action("enable_device", "已启用设备")

    @Slot()
    def _delete_device(self) -> None:
        self._device_action("delete_device", "已删除设备")

    @Slot()
    def _archive_device(self) -> None:
        self._device_action("archive_device", "已归档设备")

    def _device_action(self, method_name: str, success: str) -> None:
        code = self._require_selected_device()
        if code is None:
            return
        try:
            getattr(self._repository, method_name)(code, **self._actor_kwargs())
        except (MasterDataError, ValueError) as error:
            self._show_error(str(error))
            return
        self.refresh_devices()
        self._show_success(f"{success} {code}")

    @Slot()
    def _add_station(self) -> None:
        device = self._require_selected_device()
        if device is None:
            return
        try:
            code = self._required(self.station_code_input.text(), "站位编码")
            station = self._repository.add_station(
                device,
                code,
                name=self.station_name_input.text(),
                **self._actor_kwargs(),
            )
        except (MasterDataError, ValueError) as error:
            self._show_error(str(error))
            return
        self.station_code_input.clear()
        self.station_name_input.clear()
        self._refresh_stations(station.code)
        self._show_success(f"已新增站位 {device}/{station.code}")

    @Slot()
    def _bulk_add_stations(self) -> None:
        device = self._require_selected_device()
        if device is None:
            return
        start = self.bulk_start_input.value()
        end = self.bulk_end_input.value()
        if end < start:
            self._show_error("结束编号不能小于起始编号")
            return
        try:
            stations = self._repository.bulk_add_stations(
                device,
                self.bulk_prefix_input.text().strip(),
                start,
                end,
                width=self.bulk_width_input.value(),
                **self._actor_kwargs(),
            )
        except MasterDataError as error:
            self._show_error(str(error))
            return
        self._refresh_stations()
        self._show_success(f"已批量创建 {len(stations)} 个站位")

    @Slot()
    def _disable_station(self) -> None:
        selection = self._require_selected_station()
        if selection is None:
            return
        device, station = selection
        try:
            self._repository.disable_station(device, station, **self._actor_kwargs())
        except MasterDataError as error:
            self._show_error(str(error))
            return
        self._refresh_stations(station)
        self._show_success(f"已停用站位 {device}/{station}")

    @Slot()
    def _delete_station(self) -> None:
        selection = self._require_selected_station()
        if selection is None:
            return
        device, station = selection
        try:
            self._repository.delete_station(device, station, **self._actor_kwargs())
        except MasterDataError as error:
            self._show_error(str(error))
            return
        self._refresh_stations()
        self._show_success(f"已删除站位 {device}/{station}")

    @Slot()
    def _update_station(self) -> None:
        selection = self._require_selected_station()
        if selection is None:
            return
        device, station = selection
        try:
            actor_kwargs = self._actor_kwargs()
            was_disabled = self.enable_station_button.isEnabled()
            self._repository.update_station(
                device,
                station,
                name=self.station_name_input.text(),
                **actor_kwargs,
            )
            if was_disabled:
                self._repository.enable_station(device, station, **actor_kwargs)
        except (MasterDataError, ValueError) as error:
            self._show_error(str(error))
            return
        self._refresh_stations(station)
        self._show_success(f"已更新并启用站位 {device}/{station}")

    @Slot()
    def _enable_station(self) -> None:
        self._station_action("enable_station", "已启用站位")

    @Slot()
    def _archive_station(self) -> None:
        self._station_action("archive_station", "已归档站位")

    def _station_action(self, method_name: str, success: str) -> None:
        selection = self._require_selected_station()
        if selection is None:
            return
        device, station = selection
        try:
            getattr(self._repository, method_name)(device, station, **self._actor_kwargs())
        except (MasterDataError, ValueError) as error:
            self._show_error(str(error))
            return
        self._refresh_stations(station)
        self._show_success(f"{success} {device}/{station}")

    def _refresh_stations(self, preferred_code: str | None = None) -> None:
        device = self._current_device_code()
        if device is None:
            self.selected_device_label.setText("站位 · 尚未选择设备")
            self.station_table.setRowCount(0)
            self.station_count_label.setText("0 个")
            return

        self.selected_device_label.setText(f"站位 · 当前设备 {device}")
        stations = self._repository.search_stations(
            device,
            self.station_query_input.text(),
            enabled=self._status_filter(self.station_status_filter),
            include_archived=True,
        )
        self.station_table.setRowCount(len(stations))
        for row, station in enumerate(stations):
            self._set_row(
                self.station_table,
                row,
                (
                    station.code,
                    station.name,
                    self._enabled_text(station.enabled and not station.archived),
                    "是" if station.referenced else "否",
                ),
            )
        self.station_count_label.setText(f"{len(stations)} 个")
        target_row = next(
            (row for row, station in enumerate(stations) if station.code == preferred_code),
            0 if stations else -1,
        )
        if target_row >= 0:
            self.station_table.selectRow(target_row)
        else:
            self.station_table.clearSelection()
        self._sync_station_state_buttons()

    def _sync_device_state_buttons(self) -> None:
        row = self.device_table.currentRow()
        item = self.device_table.item(row, 3) if row >= 0 else None
        selected = item is not None
        enabled = selected and item.text() == "启用"
        self.enable_device_button.setEnabled(selected and not enabled)
        self.disable_device_button.setEnabled(enabled)

    def _sync_station_state_buttons(self) -> None:
        row = self.station_table.currentRow()
        item = self.station_table.item(row, 2) if row >= 0 else None
        selected = item is not None
        enabled = selected and item.text() == "启用"
        self.enable_station_button.setEnabled(selected and not enabled)
        self.disable_station_button.setEnabled(enabled)

    def _current_device_code(self) -> str | None:
        row = self.device_table.currentRow()
        if row < 0:
            return None
        item = self.device_table.item(row, 0)
        return item.text() if item is not None else None

    def _current_station_code(self) -> str | None:
        row = self.station_table.currentRow()
        if row < 0:
            return None
        item = self.station_table.item(row, 0)
        return item.text() if item is not None else None

    def _require_selected_device(self) -> str | None:
        device = self._current_device_code()
        if device is None:
            self._show_error("请先选择设备")
        return device

    def _require_selected_station(self) -> tuple[str, str] | None:
        device = self._require_selected_device()
        station = self._current_station_code()
        if device is None:
            return None
        if station is None:
            self._show_error("请先选择站位")
            return None
        return device, station

    def _show_success(self, message: str) -> None:
        set_feedback(self.status_label, "success", message)
        self.master_data_changed.emit()

    def _show_error(self, message: str) -> None:
        set_feedback(self.status_label, "error", message)

    @Slot(bool)
    def _toggle_bulk_panel(self, expanded: bool) -> None:
        self.bulk_group.setVisible(expanded)
        self.bulk_toggle_button.setText(
            "收起批量创建站位" if expanded else "展开批量创建站位"
        )

    @staticmethod
    def _required(value: str, label: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{label}不能为空")
        return normalized

    @staticmethod
    def _enabled_text(enabled: bool) -> str:
        return "启用" if enabled else "停用"

    def _actor_kwargs(self) -> dict[str, str]:
        if self._operator_provider is None:
            return {}
        return {"actor": self._operator_provider()}

    @staticmethod
    def _status_filter(combo: QComboBox) -> bool | None:
        return {0: None, 1: True, 2: False}[combo.currentIndex()]

    @staticmethod
    def _table(headers: tuple[str, ...]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        prepare_table(table)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        return table

    @staticmethod
    def _set_row(table: QTableWidget, row: int, values: tuple[str, ...]) -> None:
        for column, value in enumerate(values):
            table.setItem(row, column, QTableWidgetItem(value))

    @staticmethod
    def _spin_box(
        minimum: int,
        maximum: int,
        value: int,
        *,
        minimum_digits: int = 1,
    ) -> LargeStepSpinBox:
        spin_box = LargeStepSpinBox(minimum_digits=minimum_digits)
        spin_box.setRange(minimum, maximum)
        spin_box.setValue(value)
        spin_box.setAccelerated(True)
        spin_box.setMinimumHeight(42)
        return spin_box
