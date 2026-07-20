"""Product station configuration lifecycle management page."""

from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from smt_guard.bom import BomVersion
from smt_guard.configuration import ConfigurationStatus, ProductConfigurationRecord
from smt_guard.feedback import AnnouncementSink, SilentAnnouncementSink, VoicePrompt
from smt_guard.master_data import Station
from smt_guard.scan import ProductConfiguration
from smt_guard.ui.components import (
    PageHeader,
    content_card,
    prepare_table,
    section_heading,
    set_feedback,
)
from smt_guard.ui.formatting import display_datetime
from smt_guard.ui.tables import (
    UiLayoutStore,
    enable_splitter_layout,
    enable_table_layout,
    readable_item,
    set_column_widths,
    set_responsive_columns,
)


class ConfigurationRepository(Protocol):
    def list_all(self) -> list[ProductConfigurationRecord]: ...

    def validate(self, configuration: ProductConfiguration) -> list[str]: ...

    def update_draft(
        self, configuration: ProductConfiguration, *, actor: str
    ) -> ProductConfigurationRecord: ...

    def copy_version(
        self, product_code: str, version: str, new_version: str, *, actor: str
    ) -> ProductConfigurationRecord: ...

    def publish(
        self, product_code: str, version: str, *, actor: str
    ) -> ProductConfigurationRecord: ...

    def activate(
        self, product_code: str, version: str, *, actor: str
    ) -> ProductConfigurationRecord: ...

    def disable(
        self, product_code: str, version: str, *, actor: str
    ) -> ProductConfigurationRecord: ...

    def archive(
        self, product_code: str, version: str, *, actor: str
    ) -> ProductConfigurationRecord: ...


class BomVersionLookup(Protocol):
    def get_by_id(self, bom_id: int) -> BomVersion: ...


class StationResolver(Protocol):
    def resolve_station(self, station_code: str) -> Station: ...


class ConfigurationManagementWidget(QWidget):
    """Edit drafts and manage released station-configuration versions."""

    configurations_changed = Signal()
    import_requested = Signal()

    def __init__(
        self,
        repository: ConfigurationRepository,
        operator_provider: Callable[[], str],
        parent: QWidget | None = None,
        *,
        announcer: AnnouncementSink | None = None,
        bom_repository: BomVersionLookup | None = None,
        master_data: StationResolver | None = None,
        layout_store: UiLayoutStore | None = None,
    ) -> None:
        super().__init__(parent)
        self._repository = repository
        self._operator_provider = operator_provider
        self._announcer = announcer or SilentAnnouncementSink()
        self._bom_repository = bom_repository
        self._master_data = master_data
        self._layout_store = layout_store
        self._linked_boms: dict[int, BomVersion | None] = {}
        self._records: list[ProductConfigurationRecord] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(
            PageHeader(
                "产品配置",
                "导入或选择产品版本，维护站位与物料的对应关系。",
            )
        )
        filter_card = content_card(object_name="filterCard")
        filter_card.setMinimumWidth(760)
        filter_card.setMaximumWidth(980)
        filter_layout = QVBoxLayout(filter_card)
        top = QHBoxLayout()
        top.addWidget(section_heading("筛选配置"))
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("按产品编码或版本筛选")
        self.filter_input.setClearButtonEnabled(True)
        self.refresh_button = QPushButton("刷新")
        self.import_button = QPushButton("导入新配置")
        self.import_button.setProperty("actionRole", "primary")
        top.addWidget(self.filter_input, 1)
        top.addWidget(self.refresh_button)
        top.addWidget(self.import_button)
        filter_layout.addLayout(top)
        layout.addWidget(filter_card, 0, Qt.AlignmentFlag.AlignLeft)

        splitter = QSplitter()
        self.splitter = splitter
        list_card = content_card()
        list_layout = QVBoxLayout(list_card)
        list_heading = QHBoxLayout()
        list_heading.addWidget(section_heading("配置版本", "选择后在右侧查看和维护"), 1)
        self.configuration_count_chip = QLabel("0 个")
        self.configuration_count_chip.setProperty("metricChip", True)
        self.configuration_count_chip.setProperty("metricTone", "primary")
        list_heading.addWidget(self.configuration_count_chip)
        list_layout.addLayout(list_heading)
        self.configuration_table = QTableWidget(0, 5)
        self.configuration_table.setHorizontalHeaderLabels(
            ("产品编码", "配置版本", "状态", "站位数", "更新时间")
        )
        self.configuration_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        prepare_table(self.configuration_table)
        self.configuration_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.configuration_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.configuration_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        set_column_widths(self.configuration_table, (150, 140, 85, 75, 140))
        set_responsive_columns(
            self.configuration_table,
            stretch=(0, 1, 4),
            compact=(2, 3),
        )
        enable_table_layout(
            self.configuration_table,
            "configurations/list",
            self._layout_store,
            narrow_hidden=(3, 4),
            narrow_threshold=620,
        )
        list_layout.addWidget(self.configuration_table, 1)
        splitter.addWidget(list_card)
        editor = content_card(object_name="detailCard")
        editor_layout = QVBoxLayout(editor)
        editor_layout.setContentsMargins(8, 8, 8, 8)
        editor_layout.setSpacing(5)
        editor_header = QHBoxLayout()
        self.editor_label = QLabel("请选择配置")
        self.editor_label.setObjectName("detailTitle")
        self.editor_label.setWordWrap(True)
        self.editor_label.setMaximumHeight(74)
        editor_header.addWidget(self.editor_label, 1)
        summary = QHBoxLayout()
        self.configuration_status_chip = QLabel("未选择")
        self.assignment_count_chip = QLabel("站位 0")
        for chip in (self.configuration_status_chip, self.assignment_count_chip):
            chip.setProperty("metricChip", True)
        self.configuration_status_chip.setProperty("metricTone", "primary")
        summary.addWidget(self.configuration_status_chip)
        summary.addWidget(self.assignment_count_chip)
        editor_header.addLayout(summary)
        editor_layout.addLayout(editor_header)
        self.edit_hint_label = QLabel("请选择配置")
        self.edit_hint_label.setWordWrap(True)
        self.edit_hint_label.setMaximumHeight(42)
        set_feedback(self.edit_hint_label, "neutral", "请选择配置")
        editor_layout.addWidget(self.edit_hint_label)
        editor_layout.addWidget(section_heading("站位物料关系", "草稿版本可直接编辑表格"))
        self.assignment_table = QTableWidget(0, 2)
        self.assignment_table.setHorizontalHeaderLabels(("站位编码", "物料编码"))
        prepare_table(self.assignment_table)
        self.assignment_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.assignment_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        set_column_widths(self.assignment_table, (180, 280))
        set_responsive_columns(self.assignment_table, stretch=(0, 1))
        enable_table_layout(
            self.assignment_table,
            "configurations/assignments",
            self._layout_store,
        )
        self.assignment_table.setMinimumHeight(72)
        editor_layout.addWidget(self.assignment_table, 1)
        row_actions = QHBoxLayout()
        self.add_row_button = QPushButton("新增行")
        self.remove_row_button = QPushButton("删除行")
        self.save_draft_button = QPushButton("保存并校验")
        self.save_draft_button.setProperty("actionRole", "primary")
        row_actions.addWidget(self.add_row_button)
        row_actions.addWidget(self.remove_row_button)
        row_actions.addWidget(self.save_draft_button)
        self.validate_button = QPushButton("校验")
        self.validate_button.hide()
        self.activate_button = QPushButton("启用")
        self.activate_button.setProperty("actionRole", "success")
        self.disable_button = QPushButton("停用")
        self.disable_button.setProperty("actionRole", "danger")
        row_actions.addWidget(self.validate_button)
        row_actions.addWidget(self.activate_button)
        row_actions.addWidget(self.disable_button)
        editor_layout.addLayout(row_actions)
        splitter.addWidget(editor)
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)
        splitter.setSizes((720, 1080))
        enable_splitter_layout(
            splitter,
            "configurations/main",
            self._layout_store,
        )
        layout.addWidget(splitter, 1)
        self._details_stacked = False

        self.version_card = content_card(object_name="actionCard")
        lifecycle = QHBoxLayout(self.version_card)
        lifecycle.setContentsMargins(8, 8, 8, 8)
        lifecycle.addWidget(section_heading("复制为草稿并编辑"))
        self.new_version_input = QLineEdit()
        self.new_version_input.setPlaceholderText("新版本号")
        self.new_version_input.setMaximumWidth(420)
        self.copy_button = QPushButton("复制为草稿并编辑")
        self.copy_button.setProperty("actionRole", "primary")
        lifecycle.addWidget(self.new_version_input, 1)
        lifecycle.addWidget(self.copy_button)
        lifecycle.addStretch(1)
        layout.addWidget(self.version_card)
        self.version_card.hide()
        self.status_label = QLabel("就绪")
        set_feedback(self.status_label, "neutral", "就绪")
        layout.addWidget(self.status_label)

        self.refresh_button.clicked.connect(self.refresh)
        self.filter_input.returnPressed.connect(self.refresh)
        self.configuration_table.itemSelectionChanged.connect(self._render_selected)
        self.add_row_button.clicked.connect(self._add_row)
        self.remove_row_button.clicked.connect(self._remove_row)
        self.save_draft_button.clicked.connect(self._save_draft)
        self.copy_button.clicked.connect(self._copy)
        self.validate_button.clicked.connect(self._validate)
        self.activate_button.clicked.connect(self._activate_selected)
        self.disable_button.clicked.connect(self._disable_selected)
        self.import_button.clicked.connect(self.import_requested.emit)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        stacked = event.size().width() < 1050
        if stacked == self._details_stacked:
            return
        self._details_stacked = stacked
        self.splitter.setOrientation(
            Qt.Orientation.Vertical if stacked else Qt.Orientation.Horizontal
        )
        self.splitter.setSizes([1, 1] if stacked else [2, 3])

    @Slot()
    def refresh(self) -> None:
        selected = self._selected()
        selected_identity = (
            None
            if selected is None
            else (
                selected.configuration.product_code,
                selected.configuration.version,
            )
        )
        query = self.filter_input.text().strip().casefold()
        records = self._repository.list_all()
        self._linked_boms.clear()
        self._records = [
            item for item in records if not query or query in self._record_search_text(item)
        ]
        self.configuration_count_chip.setText(f"{len(self._records)} 个")
        self.configuration_table.setRowCount(len(self._records))
        for row, record in enumerate(self._records):
            configuration = record.configuration
            values = (
                configuration.product_code,
                configuration.version,
                self._status_text(record),
                str(len(configuration.assignments)),
                display_datetime(record.created_at),
            )
            for column, value in enumerate(values):
                self.configuration_table.setItem(row, column, readable_item(value))
        if self._records:
            selected_row = next(
                (
                    index
                    for index, item in enumerate(self._records)
                    if (
                        item.configuration.product_code,
                        item.configuration.version,
                    )
                    == selected_identity
                ),
                0,
            )
            self.configuration_table.selectRow(selected_row)
            self._render_selected()
        else:
            self.editor_label.setText("没有匹配的配置，请先完成导入配置")
            self.configuration_status_chip.setText("未选择")
            self.assignment_count_chip.setText("站位 0")
            self.assignment_table.setRowCount(0)
            self.activate_button.setEnabled(False)
            self.disable_button.setEnabled(False)
            self.add_row_button.setEnabled(False)
            self.remove_row_button.setEnabled(False)
            self.save_draft_button.setEnabled(False)
            self.activate_button.hide()
            self.disable_button.hide()
            self.add_row_button.hide()
            self.remove_row_button.hide()
            self.save_draft_button.hide()
            self.version_card.hide()
            set_feedback(self.edit_hint_label, "neutral", "请选择配置")

    @Slot()
    def _render_selected(self) -> None:
        record = self._selected()
        if record is None:
            self.activate_button.setEnabled(False)
            self.disable_button.setEnabled(False)
            self.add_row_button.setEnabled(False)
            self.remove_row_button.setEnabled(False)
            self.save_draft_button.setEnabled(False)
            self.activate_button.hide()
            self.disable_button.hide()
            self.add_row_button.hide()
            self.remove_row_button.hide()
            self.save_draft_button.hide()
            self.version_card.hide()
            set_feedback(self.edit_hint_label, "neutral", "请选择配置")
            return
        active = record.status is ConfigurationStatus.ACTIVE
        self.activate_button.setEnabled(not active)
        self.disable_button.setEnabled(active)
        configuration = record.configuration
        self.editor_label.setText(
            f"{configuration.product_code}/{configuration.version} | "
            f"{self._status_text(record)}\n"
            f"创建：{display_datetime(record.created_at)} by {record.created_by}"
        )
        assignments = sorted(configuration.assignments.items())
        self.configuration_status_chip.setText(self._status_text(record))
        self.configuration_status_chip.setProperty("metricTone", "success" if active else "danger")
        self.configuration_status_chip.style().unpolish(self.configuration_status_chip)
        self.configuration_status_chip.style().polish(self.configuration_status_chip)
        self.assignment_count_chip.setText(f"站位 {len(assignments)}")
        self.assignment_table.setRowCount(len(assignments))
        for row, ((_, station), material) in enumerate(assignments):
            for column, value in enumerate((station, material)):
                self.assignment_table.setItem(row, column, readable_item(value))
        editable = record.status is ConfigurationStatus.DRAFT
        self.assignment_table.setEditTriggers(
            QAbstractItemView.EditTrigger.AllEditTriggers
            if editable
            else QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.add_row_button.setEnabled(editable)
        self.remove_row_button.setEnabled(editable)
        self.save_draft_button.setEnabled(editable)
        self.add_row_button.setVisible(editable)
        self.remove_row_button.setVisible(editable)
        self.save_draft_button.setVisible(editable)
        self.activate_button.setVisible(editable)
        self.disable_button.setVisible(active)
        self.version_card.setVisible(not editable)
        locked_reason = "已启用或历史版本不能直接修改，请先复制为草稿并编辑"
        for button in (
            self.add_row_button,
            self.remove_row_button,
            self.save_draft_button,
        ):
            button.setToolTip("" if editable else locked_reason)
        if editable:
            set_feedback(
                self.edit_hint_label,
                "success",
                "当前为草稿，可新增、删除和保存站位物料关系；校验通过后再启用。",
            )
        else:
            set_feedback(
                self.edit_hint_label,
                "warning",
                "已启用或历史版本不能直接修改；如需调整，请在下方复制为草稿。",
            )

    def _linked_bom(self, record: ProductConfigurationRecord) -> BomVersion | None:
        bom_id = record.configuration.bom_version_id
        if bom_id is None or self._bom_repository is None:
            return None
        if bom_id not in self._linked_boms:
            try:
                self._linked_boms[bom_id] = self._bom_repository.get_by_id(bom_id)
            except LookupError:
                self._linked_boms[bom_id] = None
        return self._linked_boms[bom_id]

    def _record_search_text(self, record: ProductConfigurationRecord) -> str:
        configuration = record.configuration
        return f"{configuration.product_code} {configuration.version}".casefold()

    @staticmethod
    def _bom_label(bom_id: int | None, bom: BomVersion | None) -> str:
        if bom is not None:
            return bom.version
        if bom_id is None:
            return "未关联"
        return f"ID {bom_id}"

    def _selected(self) -> ProductConfigurationRecord | None:
        row = self.configuration_table.currentRow()
        return self._records[row] if 0 <= row < len(self._records) else None

    @Slot()
    def _add_row(self) -> None:
        self.assignment_table.insertRow(self.assignment_table.rowCount())

    @Slot()
    def _remove_row(self) -> None:
        row = self.assignment_table.currentRow()
        if row >= 0:
            self.assignment_table.removeRow(row)

    def _edited_configuration(self) -> ProductConfiguration:
        record = self._selected()
        if record is None:
            raise ValueError("请先选择产品配置")
        assignments: dict[tuple[str, str], str] = {}
        original = record.configuration
        original_devices = {station: device for device, station in original.assignments}
        for row in range(self.assignment_table.rowCount()):
            values: list[str] = []
            for column in range(2):
                item = self.assignment_table.item(row, column)
                values.append("" if item is None else item.text().strip())
            if not all(values):
                raise ValueError(f"第 {row + 1} 行站位和物料均不能为空")
            station, material = values
            if self._master_data is not None:
                device = self._master_data.resolve_station(station).device_code
            elif station in original_devices:
                device = original_devices[station]
            else:
                raise ValueError(f"无法确定站位 {station} 所属设备")
            key = (device, station)
            if key in assignments:
                raise ValueError(f"重复站位 {station}")
            assignments[key] = material
        return ProductConfiguration(
            original.product_code,
            original.version,
            assignments,
            original.bom_version_id,
        )

    @Slot()
    def _save_draft(self) -> None:
        try:
            configuration = self._edited_configuration()
            errors = self._repository.validate(configuration)
            if errors:
                raise ValueError("；".join(errors))
            self._repository.update_draft(configuration, actor=self._operator_provider())
        except (LookupError, ValueError) as error:
            self._show_error(str(error))
            return
        self.refresh()
        self._select_configuration(configuration.product_code, configuration.version)
        self._show_success("修改已保存，配置校验通过")
        self.configurations_changed.emit()

    @Slot()
    def _validate(self) -> None:
        try:
            configuration = self._edited_configuration()
        except ValueError as error:
            self._show_error(str(error))
            return
        errors = self._repository.validate(configuration)
        if errors:
            self._show_error("；".join(errors))
        else:
            self._show_success("配置校验通过")

    @Slot()
    def _copy(self) -> None:
        record = self._selected()
        if record is None:
            self._show_error("请先选择产品配置")
            self._announcer.announce(VoicePrompt.LIFECYCLE_FAILED)
            return
        new_version = self.new_version_input.text().strip()
        if not new_version:
            self._show_error("新版本号不能为空")
            return
        configuration = record.configuration
        try:
            self._repository.copy_version(
                configuration.product_code,
                configuration.version,
                new_version,
                actor=self._operator_provider(),
            )
        except (LookupError, ValueError) as error:
            self._show_error(str(error))
            self._announcer.announce(VoicePrompt.LIFECYCLE_FAILED)
            return
        self.new_version_input.clear()
        self.refresh()
        self._select_configuration(configuration.product_code, new_version)
        self._show_success(f"已复制新版本 {new_version}")
        self.configurations_changed.emit()

    @Slot()
    def _activate_selected(self) -> None:
        record = self._selected()
        if record is None:
            self._show_error("请先选择产品配置")
            self._announcer.announce(VoicePrompt.LIFECYCLE_FAILED)
            return
        configuration = record.configuration
        try:
            actor = self._operator_provider()
            if record.status is ConfigurationStatus.DRAFT:
                self._repository.publish(
                    configuration.product_code,
                    configuration.version,
                    actor=actor,
                )
            self._repository.activate(
                configuration.product_code,
                configuration.version,
                actor=actor,
            )
        except (LookupError, ValueError) as error:
            self._show_error(str(error))
            self._announcer.announce(VoicePrompt.LIFECYCLE_FAILED)
            return
        self.refresh()
        self._select_configuration(configuration.product_code, configuration.version)
        self._show_success(f"已启用 {configuration.product_code}/{configuration.version}")
        self._announcer.announce(VoicePrompt.CONFIGURATION_ACTIVATED)
        self.configurations_changed.emit()

    @Slot()
    def _disable_selected(self) -> None:
        record = self._selected()
        if record is None:
            self._show_error("请先选择产品配置")
            self._announcer.announce(VoicePrompt.LIFECYCLE_FAILED)
            return
        configuration = record.configuration
        try:
            self._repository.disable(
                configuration.product_code,
                configuration.version,
                actor=self._operator_provider(),
            )
        except (LookupError, ValueError) as error:
            self._show_error(str(error))
            self._announcer.announce(VoicePrompt.LIFECYCLE_FAILED)
            return
        self.refresh()
        self._select_configuration(configuration.product_code, configuration.version)
        self._show_success(f"已停用 {configuration.product_code}/{configuration.version}")
        self._announcer.announce(VoicePrompt.CONFIGURATION_DISABLED)
        self.configurations_changed.emit()

    @staticmethod
    def _status_text(record: ProductConfigurationRecord) -> str:
        if record.status is ConfigurationStatus.ACTIVE:
            return "启用"
        return "停用"

    def _select_configuration(self, product_code: str, version: str) -> None:
        for row, record in enumerate(self._records):
            configuration = record.configuration
            if configuration.product_code == product_code and configuration.version == version:
                self.configuration_table.selectRow(row)
                return

    def _show_success(self, message: str) -> None:
        set_feedback(self.status_label, "success", message)

    def _show_error(self, message: str) -> None:
        set_feedback(self.status_label, "error", message)
