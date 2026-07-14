"""Device and station management widget."""

from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
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
    QVBoxLayout,
    QWidget,
)

from smt_guard.master_data import Device, MasterDataError, Station


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


class DeviceStationWidget(QWidget):
    """Manage placement devices and their physical feeder stations."""

    master_data_changed = Signal()

    def __init__(
        self,
        repository: MasterDataRepository,
        *,
        operator_provider: Callable[[], str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._repository = repository
        self._operator_provider = operator_provider
        self._build_ui()
        self._connect_signals()
        self.refresh_devices()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("设备与站位管理")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        splitter = QSplitter()
        splitter.addWidget(self._build_device_panel())
        splitter.addWidget(self._build_station_panel())
        splitter.setSizes([480, 620])
        root.addWidget(splitter, 1)

        self.status_label = QLabel("就绪")
        self.status_label.setObjectName("feedbackLabel")
        root.addWidget(self.status_label)

    def _build_device_panel(self) -> QWidget:
        panel = QGroupBox("设备")
        layout = QVBoxLayout(panel)
        query = QHBoxLayout()
        self.device_query_input = QLineEdit()
        self.device_query_input.setPlaceholderText("按编码、名称或产线筛选")
        self.device_status_filter = QComboBox()
        self.device_status_filter.addItems(("全部状态", "启用", "停用"))
        self.device_archived_check = QCheckBox("包含归档")
        query.addWidget(self.device_query_input, 1)
        query.addWidget(self.device_status_filter)
        query.addWidget(self.device_archived_check)
        layout.addLayout(query)
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
        self.update_device_button = QPushButton("保存修改")
        self.enable_device_button = QPushButton("启用设备")
        self.disable_device_button = QPushButton("停用设备")
        self.delete_device_button = QPushButton("删除未引用")
        self.archive_device_button = QPushButton("归档设备")
        buttons.addWidget(self.add_device_button)
        buttons.addWidget(self.update_device_button)
        buttons.addWidget(self.enable_device_button)
        buttons.addWidget(self.disable_device_button)
        buttons.addWidget(self.delete_device_button)
        buttons.addWidget(self.archive_device_button)
        layout.addLayout(buttons)

        self.device_table = self._table(("设备编码", "设备名称", "产线", "状态", "归档"))
        layout.addWidget(self.device_table)
        return panel

    def _build_station_panel(self) -> QWidget:
        panel = QGroupBox("站位")
        layout = QVBoxLayout(panel)
        self.selected_device_label = QLabel("当前设备：未选择")
        layout.addWidget(self.selected_device_label)

        query = QHBoxLayout()
        self.station_query_input = QLineEdit()
        self.station_query_input.setPlaceholderText("按站位编码或名称筛选")
        self.station_status_filter = QComboBox()
        self.station_status_filter.addItems(("全部状态", "启用", "停用"))
        self.station_archived_check = QCheckBox("包含归档")
        query.addWidget(self.station_query_input, 1)
        query.addWidget(self.station_status_filter)
        query.addWidget(self.station_archived_check)
        layout.addLayout(query)

        single_form = QFormLayout()
        self.station_code_input = QLineEdit()
        self.station_name_input = QLineEdit()
        self.add_station_button = QPushButton("新增站位")
        single_form.addRow("站位编码", self.station_code_input)
        single_form.addRow("站位名称", self.station_name_input)
        single_form.addRow("", self.add_station_button)
        layout.addLayout(single_form)

        bulk_group = QGroupBox("批量新增")
        bulk_form = QFormLayout(bulk_group)
        self.bulk_prefix_input = QLineEdit("F-")
        self.bulk_start_input = self._spin_box(1, 9999, 1)
        self.bulk_end_input = self._spin_box(1, 9999, 60)
        self.bulk_width_input = self._spin_box(1, 6, 2)
        self.bulk_add_button = QPushButton("批量创建")
        bulk_form.addRow("前缀", self.bulk_prefix_input)
        bulk_form.addRow("起始编号", self.bulk_start_input)
        bulk_form.addRow("结束编号", self.bulk_end_input)
        bulk_form.addRow("数字宽度", self.bulk_width_input)
        bulk_form.addRow("", self.bulk_add_button)
        layout.addWidget(bulk_group)

        station_buttons = QHBoxLayout()
        self.update_station_button = QPushButton("保存修改")
        self.enable_station_button = QPushButton("启用站位")
        self.disable_station_button = QPushButton("停用站位")
        self.delete_station_button = QPushButton("删除未引用")
        self.archive_station_button = QPushButton("归档已引用")
        station_buttons.addWidget(self.update_station_button)
        station_buttons.addWidget(self.enable_station_button)
        station_buttons.addWidget(self.disable_station_button)
        station_buttons.addWidget(self.delete_station_button)
        station_buttons.addWidget(self.archive_station_button)
        layout.addLayout(station_buttons)

        self.station_table = self._table(("站位编码", "站位名称", "状态", "已引用", "归档"))
        layout.addWidget(self.station_table)
        return panel

    def _connect_signals(self) -> None:
        self.add_device_button.clicked.connect(self._add_device)
        self.update_device_button.clicked.connect(self._update_device)
        self.enable_device_button.clicked.connect(self._enable_device)
        self.disable_device_button.clicked.connect(self._disable_device)
        self.delete_device_button.clicked.connect(self._delete_device)
        self.archive_device_button.clicked.connect(self._archive_device)
        self.device_query_input.textChanged.connect(self._device_filter_changed)
        self.device_status_filter.currentIndexChanged.connect(self._device_filter_changed)
        self.device_archived_check.toggled.connect(self._device_filter_changed)
        self.device_table.itemSelectionChanged.connect(self._device_selection_changed)
        self.add_station_button.clicked.connect(self._add_station)
        self.update_station_button.clicked.connect(self._update_station)
        self.enable_station_button.clicked.connect(self._enable_station)
        self.bulk_add_button.clicked.connect(self._bulk_add_stations)
        self.disable_station_button.clicked.connect(self._disable_station)
        self.delete_station_button.clicked.connect(self._delete_station)
        self.archive_station_button.clicked.connect(self._archive_station)
        self.station_query_input.textChanged.connect(self._station_filter_changed)
        self.station_status_filter.currentIndexChanged.connect(self._station_filter_changed)
        self.station_archived_check.toggled.connect(self._station_filter_changed)
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
            include_archived=self.device_archived_check.isChecked(),
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
                    self._enabled_text(device.enabled),
                    "是" if device.archived else "否",
                ),
            )
        self.device_table.blockSignals(False)

        target_row = next(
            (row for row, device in enumerate(devices) if device.code == selected),
            0 if devices else -1,
        )
        if target_row >= 0:
            self.device_table.selectRow(target_row)
        else:
            self.device_table.clearSelection()
            self._refresh_stations()

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
        self._refresh_stations()

    @Slot()
    def _station_selection_changed(self) -> None:
        row = self.station_table.currentRow()
        if row < 0:
            return
        code = self.station_table.item(row, 0)
        name = self.station_table.item(row, 1)
        self.station_code_input.setText("" if code is None else code.text())
        self.station_name_input.setText("" if name is None else name.text())

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
            self._repository.update_device(
                code,
                name=self._required(self.device_name_input.text(), "设备名称"),
                line=self.device_line_input.text(),
                **self._actor_kwargs(),
            )
        except (MasterDataError, ValueError) as error:
            self._show_error(str(error))
            return
        self.refresh_devices(code)
        self._show_success(f"已更新设备 {code}")

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
            self._repository.update_station(
                device,
                station,
                name=self.station_name_input.text(),
                **self._actor_kwargs(),
            )
        except (MasterDataError, ValueError) as error:
            self._show_error(str(error))
            return
        self._refresh_stations(station)
        self._show_success(f"已更新站位 {device}/{station}")

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
            self.selected_device_label.setText("当前设备：未选择")
            self.station_table.setRowCount(0)
            return

        self.selected_device_label.setText(f"当前设备：{device}")
        stations = self._repository.search_stations(
            device,
            self.station_query_input.text(),
            enabled=self._status_filter(self.station_status_filter),
            include_archived=self.station_archived_check.isChecked(),
        )
        self.station_table.setRowCount(len(stations))
        for row, station in enumerate(stations):
            self._set_row(
                self.station_table,
                row,
                (
                    station.code,
                    station.name,
                    self._enabled_text(station.enabled),
                    "是" if station.referenced else "否",
                    "是" if station.archived else "否",
                ),
            )
        target_row = next(
            (row for row, station in enumerate(stations) if station.code == preferred_code),
            0 if stations else -1,
        )
        if target_row >= 0:
            self.station_table.selectRow(target_row)
        else:
            self.station_table.clearSelection()

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
        self.status_label.setProperty("feedbackState", "success")
        self.status_label.setStyleSheet("color: #18794e;")
        self.status_label.setText(message)
        self.master_data_changed.emit()

    def _show_error(self, message: str) -> None:
        self.status_label.setProperty("feedbackState", "error")
        self.status_label.setStyleSheet("color: #b42318;")
        self.status_label.setText(message)

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
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        return table

    @staticmethod
    def _set_row(table: QTableWidget, row: int, values: tuple[str, ...]) -> None:
        for column, value in enumerate(values):
            table.setItem(row, column, QTableWidgetItem(value))

    @staticmethod
    def _spin_box(minimum: int, maximum: int, value: int) -> QSpinBox:
        spin_box = QSpinBox()
        spin_box.setRange(minimum, maximum)
        spin_box.setValue(value)
        return spin_box
