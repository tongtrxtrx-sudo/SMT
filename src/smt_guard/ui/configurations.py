"""Product station configuration lifecycle management page."""

from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import Signal, Slot
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

from smt_guard.configuration import ConfigurationStatus, ProductConfigurationRecord
from smt_guard.feedback import AnnouncementSink, SilentAnnouncementSink, VoicePrompt
from smt_guard.scan import ProductConfiguration
from smt_guard.ui.tables import readable_item, set_column_widths


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


class ConfigurationManagementWidget(QWidget):
    """Edit drafts and manage released station-configuration versions."""

    configurations_changed = Signal()

    def __init__(
        self,
        repository: ConfigurationRepository,
        operator_provider: Callable[[], str],
        parent: QWidget | None = None,
        *,
        announcer: AnnouncementSink | None = None,
    ) -> None:
        super().__init__(parent)
        self._repository = repository
        self._operator_provider = operator_provider
        self._announcer = announcer or SilentAnnouncementSink()
        self._records: list[ProductConfigurationRecord] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("产品站位配置管理")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        top = QHBoxLayout()
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("按产品或版本筛选")
        self.refresh_button = QPushButton("刷新")
        top.addWidget(self.filter_input, 1)
        top.addWidget(self.refresh_button)
        layout.addLayout(top)

        splitter = QSplitter()
        self.configuration_table = QTableWidget(0, 6)
        self.configuration_table.setHorizontalHeaderLabels(
            ("产品", "版本", "状态", "BOM 版本 ID", "创建时间", "创建人")
        )
        self.configuration_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.configuration_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.configuration_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.configuration_table.verticalHeader().setVisible(False)
        set_column_widths(self.configuration_table, (120, 170, 90, 120, 190, 120))
        splitter.addWidget(self.configuration_table)
        editor = QWidget()
        editor_layout = QVBoxLayout(editor)
        self.editor_label = QLabel("请选择配置")
        editor_layout.addWidget(self.editor_label)
        self.assignment_table = QTableWidget(0, 3)
        self.assignment_table.setHorizontalHeaderLabels(("设备编码", "站位编码", "物料编码"))
        self.assignment_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        set_column_widths(self.assignment_table, (150, 150, 240))
        editor_layout.addWidget(self.assignment_table, 1)
        row_actions = QHBoxLayout()
        self.add_row_button = QPushButton("新增行")
        self.remove_row_button = QPushButton("删除行")
        self.save_draft_button = QPushButton("保存修改")
        row_actions.addWidget(self.add_row_button)
        row_actions.addWidget(self.remove_row_button)
        row_actions.addWidget(self.save_draft_button)
        editor_layout.addLayout(row_actions)
        splitter.addWidget(editor)
        splitter.setSizes((600, 600))
        layout.addWidget(splitter, 1)

        lifecycle = QHBoxLayout()
        self.new_version_input = QLineEdit()
        self.new_version_input.setPlaceholderText("新版本号")
        self.copy_button = QPushButton("复制新版本")
        self.validate_button = QPushButton("校验")
        self.activate_button = QPushButton("启用")
        self.disable_button = QPushButton("停用")
        lifecycle.addWidget(self.new_version_input)
        for button in (
            self.copy_button,
            self.validate_button,
            self.activate_button,
            self.disable_button,
        ):
            lifecycle.addWidget(button)
        layout.addLayout(lifecycle)
        self.status_label = QLabel("就绪")
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

    @Slot()
    def refresh(self) -> None:
        query = self.filter_input.text().strip().casefold()
        records = self._repository.list_all()
        self._records = [
            item
            for item in records
            if not query
            or query in item.configuration.product_code.casefold()
            or query in item.configuration.version.casefold()
        ]
        self.configuration_table.setRowCount(len(self._records))
        for row, record in enumerate(self._records):
            configuration = record.configuration
            values = (
                configuration.product_code,
                configuration.version,
                self._status_text(record),
                "" if configuration.bom_version_id is None else str(configuration.bom_version_id),
                record.created_at.isoformat(),
                record.created_by,
            )
            for column, value in enumerate(values):
                self.configuration_table.setItem(row, column, readable_item(value))
        if self._records:
            self.configuration_table.selectRow(0)
            self._render_selected()
        else:
            self.editor_label.setText("没有匹配的配置")
            self.assignment_table.setRowCount(0)
            self.activate_button.setEnabled(False)
            self.disable_button.setEnabled(False)

    @Slot()
    def _render_selected(self) -> None:
        record = self._selected()
        if record is None:
            self.activate_button.setEnabled(False)
            self.disable_button.setEnabled(False)
            return
        active = record.status is ConfigurationStatus.ACTIVE
        self.activate_button.setEnabled(not active)
        self.disable_button.setEnabled(active)
        configuration = record.configuration
        self.editor_label.setText(
            f"{configuration.product_code}/{configuration.version} | "
            f"{self._status_text(record)} | "
            f"创建人 {record.created_by}"
        )
        assignments = sorted(configuration.assignments.items())
        self.assignment_table.setRowCount(len(assignments))
        for row, ((device, station), material) in enumerate(assignments):
            for column, value in enumerate((device, station, material)):
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
        for row in range(self.assignment_table.rowCount()):
            values: list[str] = []
            for column in range(3):
                item = self.assignment_table.item(row, column)
                values.append("" if item is None else item.text().strip())
            if not all(values):
                raise ValueError(f"第 {row + 1} 行设备、站位和物料均不能为空")
            key = (values[0], values[1])
            if key in assignments:
                raise ValueError(f"重复站位 {values[0]}/{values[1]}")
            assignments[key] = values[2]
        original = record.configuration
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
            self._repository.update_draft(configuration, actor=self._operator_provider())
        except (LookupError, ValueError) as error:
            self._show_error(str(error))
            return
        self.refresh()
        self._select_configuration(configuration.product_code, configuration.version)
        self._show_success("修改已保存")
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
        self._show_success(
            f"已启用 {configuration.product_code}/{configuration.version}"
        )
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
        self._show_success(
            f"已停用 {configuration.product_code}/{configuration.version}"
        )
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
        self.status_label.setStyleSheet("color: #18794e;")
        self.status_label.setText(message)

    def _show_error(self, message: str) -> None:
        self.status_label.setStyleSheet("color: #b42318;")
        self.status_label.setText(message)
