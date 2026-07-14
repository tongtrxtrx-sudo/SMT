"""Versioned BOM lifecycle management page."""

from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from smt_guard.bom import BomVersion


class BomRepository(Protocol):
    def list_versions(self, product_code: str | None = None) -> list[BomVersion]: ...

    def publish(self, product_code: str, version: str, *, actor: str) -> BomVersion: ...

    def activate(self, product_code: str, version: str, *, actor: str) -> BomVersion: ...

    def obsolete(self, product_code: str, version: str, *, actor: str) -> BomVersion: ...

    def archive(self, product_code: str, version: str, *, actor: str) -> BomVersion: ...

    def compare(self, first_id: int, second_id: int) -> dict[str, object]: ...


class BomManagementWidget(QWidget):
    """Inspect provenance, compare versions, and perform BOM lifecycle actions."""

    bom_changed = Signal()
    HEADERS = ("产品", "版本", "状态", "来源文件", "SHA-256", "导入时间", "操作人")

    def __init__(
        self,
        repository: BomRepository,
        operator_provider: Callable[[], str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._repository = repository
        self._operator_provider = operator_provider
        self._versions: list[BomVersion] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("BOM 版本管理")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        query = QHBoxLayout()
        self.product_filter = QLineEdit()
        self.product_filter.setPlaceholderText("按产品编码筛选")
        self.refresh_button = QPushButton("刷新")
        query.addWidget(self.product_filter, 1)
        query.addWidget(self.refresh_button)
        layout.addLayout(query)

        splitter = QSplitter()
        self.version_table = QTableWidget(0, len(self.HEADERS))
        self.version_table.setHorizontalHeaderLabels(self.HEADERS)
        self.version_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.version_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.version_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.version_table.verticalHeader().setVisible(False)
        splitter.addWidget(self.version_table)
        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        self.detail_label = QLabel("请选择 BOM 版本")
        self.detail_label.setWordWrap(True)
        detail_layout.addWidget(self.detail_label)
        self.material_table = QTableWidget(0, 5)
        self.material_table.setHorizontalHeaderLabels(
            ("物料编码", "名称", "规格", "单位用量", "分类")
        )
        self.material_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        detail_layout.addWidget(self.material_table, 1)
        splitter.addWidget(detail)
        splitter.setSizes((700, 500))
        layout.addWidget(splitter, 1)

        actions = QHBoxLayout()
        self.publish_button = QPushButton("发布")
        self.activate_button = QPushButton("启用")
        self.obsolete_button = QPushButton("作废")
        self.archive_button = QPushButton("归档")
        for button in (
            self.publish_button,
            self.activate_button,
            self.obsolete_button,
            self.archive_button,
        ):
            actions.addWidget(button)
        actions.addStretch(1)
        layout.addLayout(actions)

        compare = QHBoxLayout()
        self.compare_first = QComboBox()
        self.compare_second = QComboBox()
        self.compare_button = QPushButton("比较版本")
        self.compare_label = QLabel("请选择两个版本")
        compare.addWidget(self.compare_first)
        compare.addWidget(self.compare_second)
        compare.addWidget(self.compare_button)
        compare.addWidget(self.compare_label, 1)
        layout.addLayout(compare)
        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)

        self.refresh_button.clicked.connect(self.refresh)
        self.product_filter.returnPressed.connect(self.refresh)
        self.version_table.itemSelectionChanged.connect(self._render_selected)
        self.publish_button.clicked.connect(lambda: self._transition("publish", "已发布"))
        self.activate_button.clicked.connect(lambda: self._transition("activate", "已启用"))
        self.obsolete_button.clicked.connect(lambda: self._transition("obsolete", "已作废"))
        self.archive_button.clicked.connect(lambda: self._transition("archive", "已归档"))
        self.compare_button.clicked.connect(self._compare)

    @Slot()
    def refresh(self) -> None:
        product = self.product_filter.text().strip()
        self._versions = self._repository.list_versions(product or None)
        self.version_table.setRowCount(len(self._versions))
        self.compare_first.clear()
        self.compare_second.clear()
        for row, version in enumerate(self._versions):
            values = (
                version.document.product.material_code,
                version.version,
                version.status.value,
                version.source_filename,
                version.source_sha256,
                version.imported_at.isoformat(),
                version.imported_by,
            )
            for column, value in enumerate(values):
                self.version_table.setItem(row, column, QTableWidgetItem(value))
            label = f"{values[0]} / {version.version}"
            self.compare_first.addItem(label, version.id)
            self.compare_second.addItem(label, version.id)
        if self._versions:
            self.version_table.selectRow(0)
            if len(self._versions) > 1:
                self.compare_second.setCurrentIndex(1)
        else:
            self.detail_label.setText("没有匹配的 BOM 版本")
            self.material_table.setRowCount(0)

    @Slot()
    def _render_selected(self) -> None:
        version = self._selected()
        if version is None:
            return
        product = version.document.product
        self.detail_label.setText(
            f"产品：{product.material_code} {product.name}\n"
            f"BOM：{product.bom_number} {product.bom_name}\n"
            f"规格：{product.specification}\n来源：{version.source_filename}\n"
            f"SHA-256：{version.source_sha256}\n导入：{version.imported_at.isoformat()} "
            f"by {version.imported_by}"
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
                self.material_table.setItem(row, column, QTableWidgetItem(value))

    def _selected(self) -> BomVersion | None:
        row = self.version_table.currentRow()
        return self._versions[row] if 0 <= row < len(self._versions) else None

    def _transition(self, operation: str, success: str) -> None:
        version = self._selected()
        if version is None:
            self._show_error("请先选择 BOM 版本")
            return
        product = version.document.product.material_code
        try:
            getattr(self._repository, operation)(
                product, version.version, actor=self._operator_provider()
            )
        except (LookupError, ValueError) as error:
            self._show_error(str(error))
            return
        self.refresh()
        self._show_success(f"{success} {product}/{version.version}")
        self.bom_changed.emit()

    @Slot()
    def _compare(self) -> None:
        first = self.compare_first.currentData()
        second = self.compare_second.currentData()
        if not isinstance(first, int) or not isinstance(second, int):
            self._show_error("请选择两个 BOM 版本")
            return
        comparison = self._repository.compare(first, second)
        self.compare_label.setText(
            "新增：{added}；删除：{removed}；变化：{changed}".format(
                added=", ".join(comparison["added"]) or "无",  # type: ignore[arg-type]
                removed=", ".join(comparison["removed"]) or "无",  # type: ignore[arg-type]
                changed=", ".join(comparison["changed"]) or "无",  # type: ignore[arg-type]
            )
        )

    def _show_success(self, message: str) -> None:
        self.status_label.setStyleSheet("color: #18794e;")
        self.status_label.setText(message)

    def _show_error(self, message: str) -> None:
        self.status_label.setStyleSheet("color: #b42318;")
        self.status_label.setText(message)
