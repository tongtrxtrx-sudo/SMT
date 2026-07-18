"""Versioned BOM lifecycle management page."""

from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from smt_guard.bom import BomStatus, BomVersion
from smt_guard.feedback import AnnouncementSink, SilentAnnouncementSink
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


class BomRepository(Protocol):
    def list_versions(self, product_code: str | None = None) -> list[BomVersion]: ...

    def compare(self, first_id: int, second_id: int) -> dict[str, object]: ...


class BomManagementWidget(QWidget):
    """Inspect BOM provenance and compare automatically managed versions."""

    bom_changed = Signal()
    import_requested = Signal()
    HEADERS = ("产品", "版本", "版本定位", "物料数", "导入时间")

    def __init__(
        self,
        repository: BomRepository,
        operator_provider: Callable[[], str],
        parent: QWidget | None = None,
        *,
        announcer: AnnouncementSink | None = None,
        layout_store: UiLayoutStore | None = None,
    ) -> None:
        super().__init__(parent)
        self._repository = repository
        self._operator_provider = operator_provider
        self._announcer = announcer or SilentAnnouncementSink()
        self._layout_store = layout_store
        self._versions: list[BomVersion] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(
            PageHeader(
                "BOM 版本",
                "当前版本由导入配置流程自动切换；是否允许扫码由产品配置控制。",
            )
        )
        query_card = content_card(object_name="filterCard")
        query_card.setMinimumWidth(760)
        query_card.setMaximumWidth(980)
        query_layout = QVBoxLayout(query_card)
        query = QHBoxLayout()
        query.addWidget(section_heading("筛选 BOM"))
        self.product_filter = QLineEdit()
        self.product_filter.setPlaceholderText("按产品编码筛选")
        self.product_filter.setClearButtonEnabled(True)
        self.refresh_button = QPushButton("刷新")
        query.addWidget(self.product_filter, 1)
        query.addWidget(self.refresh_button)
        query_layout.addLayout(query)
        layout.addWidget(query_card, 0, Qt.AlignmentFlag.AlignLeft)

        splitter = QSplitter()
        self.splitter = splitter
        version_card = content_card()
        version_layout = QVBoxLayout(version_card)
        version_heading = QHBoxLayout()
        version_heading.addWidget(section_heading("版本列表", "选择版本查看物料和来源"), 1)
        self.version_count_chip = QLabel("0 个")
        self.version_count_chip.setProperty("metricChip", True)
        self.version_count_chip.setProperty("metricTone", "primary")
        version_heading.addWidget(self.version_count_chip)
        version_layout.addLayout(version_heading)
        self.version_table = QTableWidget(0, len(self.HEADERS))
        self.version_table.setHorizontalHeaderLabels(self.HEADERS)
        prepare_table(self.version_table)
        self.version_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.version_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.version_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.version_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.version_table.verticalHeader().setVisible(False)
        set_column_widths(self.version_table, (120, 150, 80, 70, 130))
        set_responsive_columns(
            self.version_table,
            stretch=(0, 4),
            compact=(2, 3),
        )
        enable_table_layout(
            self.version_table,
            "boms/versions",
            self._layout_store,
            narrow_hidden=(2, 4),
            narrow_threshold=620,
        )
        version_layout.addWidget(self.version_table, 1)
        splitter.addWidget(version_card)
        detail = content_card(object_name="detailCard")
        detail.setMinimumWidth(520)
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(8, 8, 8, 8)
        detail_layout.setSpacing(5)
        detail_layout.addWidget(section_heading("版本详情", "低频来源信息与物料清单集中展示"))
        metrics = QHBoxLayout()
        self.bom_status_chip = QLabel("未选择")
        self.bom_material_chip = QLabel("物料 0")
        for chip in (self.bom_status_chip, self.bom_material_chip):
            chip.setProperty("metricChip", True)
        self.bom_status_chip.setProperty("metricTone", "primary")
        metrics.addWidget(self.bom_status_chip)
        metrics.addWidget(self.bom_material_chip)
        metrics.addStretch(1)
        detail_layout.addLayout(metrics)
        self.detail_label = QLabel("请选择 BOM 版本")
        self.detail_label.setWordWrap(True)
        self.detail_label.setStyleSheet("font-size: 13px;")
        self.detail_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Minimum,
        )
        self.detail_scroll = QScrollArea()
        self.detail_scroll.setWidgetResizable(True)
        self.detail_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.detail_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.detail_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.detail_scroll.setMinimumHeight(82)
        self.detail_scroll.setMaximumHeight(92)
        self.detail_scroll.setWidget(self.detail_label)
        detail_layout.addWidget(self.detail_scroll)
        self.import_button = QPushButton("导入第一个 BOM")
        self.import_button.setProperty("actionRole", "primary")
        self.import_button.hide()
        detail_layout.addWidget(self.import_button)
        self.lifecycle_hint_label = QLabel("请选择 BOM 版本")
        self.lifecycle_hint_label.setWordWrap(True)
        self.lifecycle_hint_label.setMaximumHeight(42)
        set_feedback(self.lifecycle_hint_label, "neutral", "请选择 BOM 版本")
        detail_layout.addWidget(self.lifecycle_hint_label)
        detail_layout.addWidget(section_heading("物料明细"))
        self.material_table = QTableWidget(0, 5)
        self.material_table.setHorizontalHeaderLabels(
            ("物料编码", "名称", "规格", "单位用量", "分类")
        )
        prepare_table(self.material_table)
        self.material_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.material_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        set_column_widths(self.material_table, (130, 100, 180, 70, 120))
        set_responsive_columns(
            self.material_table,
            stretch=(0, 1, 2, 4),
            compact=(3,),
        )
        enable_table_layout(
            self.material_table,
            "boms/materials",
            self._layout_store,
        )
        self.material_table.setMinimumHeight(72)
        detail_layout.addWidget(self.material_table, 1)
        splitter.addWidget(detail)
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)
        splitter.setSizes((720, 1080))
        enable_splitter_layout(splitter, "boms/main", self._layout_store)
        layout.addWidget(splitter, 1)

        compare_card = content_card(object_name="actionCard")
        compare = QHBoxLayout(compare_card)
        compare.setContentsMargins(8, 8, 8, 8)
        compare.addWidget(section_heading("版本比较"))
        self.compare_first = QComboBox()
        self.compare_second = QComboBox()
        self.compare_button = QPushButton("比较版本")
        self.compare_button.setEnabled(False)
        self.compare_label = QLabel("请选择两个版本")
        compare.addWidget(self.compare_first)
        compare.addWidget(self.compare_second)
        compare.addWidget(self.compare_button)
        compare.addWidget(self.compare_label, 1)
        layout.addWidget(compare_card)
        self.status_label = QLabel("就绪")
        set_feedback(self.status_label, "neutral", "就绪")
        layout.addWidget(self.status_label)

        self.refresh_button.clicked.connect(self.refresh)
        self.product_filter.returnPressed.connect(self.refresh)
        self.version_table.itemSelectionChanged.connect(self._render_selected)
        self.compare_first.currentIndexChanged.connect(
            self._refresh_compare_second
        )
        self.compare_button.clicked.connect(self._compare)
        self.import_button.clicked.connect(self.import_requested.emit)

    @Slot()
    def refresh(self) -> None:
        product = self.product_filter.text().strip()
        self._versions = self._repository.list_versions(product or None)
        self.version_count_chip.setText(f"{len(self._versions)} 个")
        self.version_table.setRowCount(len(self._versions))
        self.compare_first.blockSignals(True)
        self.compare_first.clear()
        self.compare_second.clear()
        for row, version in enumerate(self._versions):
            values = (
                version.document.product.material_code,
                version.version,
                self._status_text(version),
                len(version.document.materials),
                display_datetime(version.imported_at),
            )
            for column, value in enumerate(values):
                self.version_table.setItem(row, column, readable_item(value))
            label = f"{values[0]} / {version.version}"
            self.compare_first.addItem(label, version.id)
        self.compare_first.blockSignals(False)
        self._refresh_compare_second()
        if self._versions:
            self.import_button.hide()
            self.version_table.selectRow(0)
            self._render_selected()
            self.status_label.setText(f"找到 {len(self._versions)} 个 BOM 版本")
        else:
            self.detail_label.setText("没有匹配的 BOM 版本，请先导入 BOM")
            self.bom_status_chip.setText("未选择")
            self.bom_material_chip.setText("物料 0")
            self.import_button.show()
            self.material_table.setRowCount(0)
            set_feedback(self.lifecycle_hint_label, "neutral", "请选择 BOM 版本")
            self.status_label.setText("没有匹配的 BOM 版本")

    @Slot()
    def _refresh_compare_second(self) -> None:
        first = self._version_for_id(self.compare_first.currentData())
        previous_second = self.compare_second.currentData()
        self.compare_second.blockSignals(True)
        self.compare_second.clear()
        if first is not None:
            product_code = first.document.product.material_code
            for version in self._versions:
                if (
                    version.id != first.id
                    and version.document.product.material_code == product_code
                ):
                    self.compare_second.addItem(
                        f"{product_code} / {version.version}",
                        version.id,
                    )
        previous_index = self.compare_second.findData(previous_second)
        if previous_index >= 0:
            self.compare_second.setCurrentIndex(previous_index)
        self.compare_second.blockSignals(False)
        can_compare = self.compare_second.count() > 0
        self.compare_second.setEnabled(can_compare)
        self.compare_button.setEnabled(can_compare)
        self.compare_label.setText(
            "请选择同一产品的另一个版本"
            if can_compare
            else "该产品暂无其他版本可比较"
        )

    def _version_for_id(self, version_id: object) -> BomVersion | None:
        if not isinstance(version_id, int):
            return None
        return next(
            (version for version in self._versions if version.id == version_id),
            None,
        )

    @Slot()
    def _render_selected(self) -> None:
        version = self._selected()
        if version is None:
            return
        active = version.status is BomStatus.ACTIVE
        product = version.document.product
        self.bom_status_chip.setText(self._status_text(version))
        self.bom_status_chip.setProperty(
            "metricTone", "success" if active else "primary"
        )
        self.bom_status_chip.style().unpolish(self.bom_status_chip)
        self.bom_status_chip.style().polish(self.bom_status_chip)
        self.bom_material_chip.setText(f"物料 {len(version.document.materials)}")
        if active:
            set_feedback(
                self.lifecycle_hint_label,
                "success",
                "这是该产品的当前 BOM 版本。导入并启用新配置后，当前版本会自动切换。",
            )
        else:
            set_feedback(
                self.lifecycle_hint_label,
                "neutral",
                "这是历史或待配置版本，可用于比较与追溯；它不会单独决定是否允许扫码。",
            )
        short_sha = (
            version.source_sha256
            if len(version.source_sha256) <= 36
            else f"{version.source_sha256[:18]}…{version.source_sha256[-14:]}"
        )
        detail = (
            f"产品：{product.material_code} {product.name} | "
            f"BOM：{product.bom_number} {product.bom_name}\n"
            f"规格：{product.specification}\n"
            f"来源：{version.source_filename} | "
            f"导入：{display_datetime(version.imported_at)} by {version.imported_by}\n"
            f"SHA-256：{short_sha}"
        )
        self.detail_label.setText(detail)
        self.detail_label.setToolTip(
            detail.replace(short_sha, version.source_sha256)
        )
        materials = sorted(version.document.materials.values(), key=lambda item: item.code)
        self.material_table.setRowCount(len(materials))
        for row, material in enumerate(materials):
            for column, value in enumerate(
                (
                    material.code,
                    material.name,
                    material.specification,
                    material.quantity,
                    material.category,
                )
            ):
                self.material_table.setItem(row, column, readable_item(value))

    def _selected(self) -> BomVersion | None:
        row = self.version_table.currentRow()
        return self._versions[row] if 0 <= row < len(self._versions) else None

    @staticmethod
    def _status_text(version: BomVersion) -> str:
        if version.status is BomStatus.ACTIVE:
            return "当前版本"
        return "历史版本"

    @Slot()
    def _compare(self) -> None:
        first = self.compare_first.currentData()
        second = self.compare_second.currentData()
        if not isinstance(first, int) or not isinstance(second, int):
            self._show_error("请选择两个 BOM 版本")
            return
        first_version = self._version_for_id(first)
        second_version = self._version_for_id(second)
        if first_version is None or second_version is None:
            self._show_error("请选择两个有效的 BOM 版本")
            return
        if (
            first_version.document.product.material_code
            != second_version.document.product.material_code
        ):
            self._show_error("只能比较同一产品的 BOM 版本")
            return
        comparison = self._repository.compare(first, second)
        self.compare_label.setText(
            "新增：{added}；删除：{removed}；变化：{changed}".format(
                added=", ".join(comparison["added"]) or "无",  # type: ignore[arg-type]
                removed=", ".join(comparison["removed"]) or "无",  # type: ignore[arg-type]
                changed=", ".join(comparison["changed"]) or "无",  # type: ignore[arg-type]
            )
        )

    def _show_error(self, message: str) -> None:
        set_feedback(self.status_label, "error", message)
