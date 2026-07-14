"""Verification record query and CSV export widget."""

from pathlib import Path
from typing import Protocol

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from smt_guard.records import Attempt


class AttemptReader(Protocol):
    """Read attempts for one run."""

    def list_for_run(self, run_id: str) -> list[Attempt]:
        """Return attempts in identifier order."""
        ...


class RunExporter(Protocol):
    """Export one run to a selected path."""

    def export_run(self, run_id: str, path: Path) -> None:
        """Write one run's records."""
        ...


class RecordQueryWidget(QWidget):
    """Query exact run identifiers and export their attempt history."""

    HEADERS = (
        "编号",
        "时间",
        "运行编号",
        "产品",
        "版本",
        "设备",
        "站位",
        "要求物料",
        "扫码物料",
        "结果",
        "重复",
    )

    def __init__(
        self,
        repository: AttemptReader,
        exporter: RunExporter,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._repository = repository
        self._exporter = exporter
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("扫码记录查询"))

        query_row = QHBoxLayout()
        self.run_id_input = QLineEdit()
        self.run_id_input.setPlaceholderText("输入运行编号")
        self.query_button = QPushButton("查询")
        query_row.addWidget(self.run_id_input, 1)
        query_row.addWidget(self.query_button)
        layout.addLayout(query_row)

        export_row = QHBoxLayout()
        self.export_path_input = QLineEdit()
        self.export_path_input.setPlaceholderText("选择 CSV 导出路径")
        self.export_browse_button = QPushButton("选择路径")
        self.export_button = QPushButton("导出当前运行")
        export_row.addWidget(self.export_path_input, 1)
        export_row.addWidget(self.export_browse_button)
        export_row.addWidget(self.export_button)
        layout.addLayout(export_row)

        self.record_table = QTableWidget(0, len(self.HEADERS))
        self.record_table.setHorizontalHeaderLabels(self.HEADERS)
        self.record_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.record_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.record_table.verticalHeader().setVisible(False)
        layout.addWidget(self.record_table, 1)

        self.status_label = QLabel("请输入运行编号")
        layout.addWidget(self.status_label)

    def _connect_signals(self) -> None:
        self.query_button.clicked.connect(self._query)
        self.run_id_input.returnPressed.connect(self._query)
        self.export_browse_button.clicked.connect(self._select_export_path)
        self.export_button.clicked.connect(self._export)

    @Slot()
    def _query(self) -> None:
        try:
            run_id = self._required(self.run_id_input.text(), "运行编号")
        except ValueError as error:
            self._show_error(str(error))
            return
        records = self._repository.list_for_run(run_id)
        self._render_records(records)
        if records:
            self._show_success(f"找到 {len(records)} 条记录")
        else:
            self._show_neutral(f"未找到运行 {run_id} 的记录")

    @Slot()
    def _select_export_path(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出扫码记录",
            self.export_path_input.text().strip(),
            "CSV 文件 (*.csv)",
        )
        if path:
            self.export_path_input.setText(path)

    @Slot()
    def _export(self) -> None:
        try:
            run_id = self._required(self.run_id_input.text(), "运行编号")
            path = Path(self._required(self.export_path_input.text(), "导出路径"))
            self._exporter.export_run(run_id, path)
        except (OSError, ValueError) as error:
            self._show_error(str(error))
            return
        self._show_success(f"已导出运行 {run_id} 到 {path}")

    def _render_records(self, records: list[Attempt]) -> None:
        self.record_table.setRowCount(len(records))
        for row, attempt in enumerate(records):
            values = (
                str(attempt.id or ""),
                attempt.timestamp.isoformat(),
                attempt.run_id,
                attempt.product_code,
                attempt.product_version,
                attempt.device_code,
                attempt.station_code,
                attempt.expected_material,
                attempt.scanned_material,
                attempt.result.value,
                "是" if attempt.repeated else "否",
            )
            for column, value in enumerate(values):
                self.record_table.setItem(row, column, QTableWidgetItem(value))

    def _show_success(self, message: str) -> None:
        self.status_label.setProperty("feedbackState", "success")
        self.status_label.setStyleSheet("color: #18794e;")
        self.status_label.setText(message)

    def _show_neutral(self, message: str) -> None:
        self.status_label.setProperty("feedbackState", "neutral")
        self.status_label.setStyleSheet("color: #344054;")
        self.status_label.setText(message)

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
