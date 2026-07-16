"""Top-level navigation window for SMT Guard."""

import os
from pathlib import Path

from PySide6.QtCore import QTimer, Slot
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QMainWindow, QTableWidget, QTabWidget, QVBoxLayout, QWidget

from smt_guard.ui.operator import OperatorSessionWidget
from smt_guard.ui.scanning import ScanWidget

APPLICATION_STYLE = """
QWidget {
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
    font-size: 14px;
    color: #1d2939;
    background-color: #f8fafc;
}
QMainWindow, QTabWidget, QTabWidget::pane, QTabBar {
    background-color: #f8fafc;
}
QTabBar::tab {
    background-color: #eaecf0;
    border: 1px solid #d0d5dd;
    padding: 8px 18px;
}
QTabBar::tab:selected {
    background-color: #ffffff;
    color: #175cd3;
}
QGroupBox {
    border: 1px solid #d0d5dd;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 8px;
    background-color: #ffffff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
QLineEdit, QSpinBox, QComboBox, QDateTimeEdit, QTableWidget {
    background-color: #ffffff;
    color: #1d2939;
    border: 1px solid #98a2b3;
    border-radius: 4px;
    padding: 5px;
    selection-background-color: #d1e9ff;
    selection-color: #102a56;
}
QAbstractItemView {
    background-color: #ffffff;
    color: #1d2939;
}
QTableWidget {
    gridline-color: #d0d5dd;
    alternate-background-color: #f9fafb;
}
QTableWidget::item {
    background-color: #ffffff;
    color: #1d2939;
}
QTableWidget::item:selected {
    background-color: #d1e9ff;
    color: #102a56;
}
QHeaderView::section, QTableCornerButton::section {
    background-color: #eaecf0;
    color: #344054;
    border: 1px solid #d0d5dd;
    padding: 6px;
    font-weight: 600;
}
QPushButton {
    background-color: #ffffff;
    color: #344054;
    border: 1px solid #98a2b3;
    border-radius: 4px;
    padding: 7px 14px;
}
QPushButton:hover {
    background-color: #f2f4f7;
}
QPushButton[actionRole="primary"] {
    background-color: #175cd3;
    color: #ffffff;
    border-color: #175cd3;
}
QPushButton[actionRole="primary"]:hover {
    background-color: #1849a9;
}
QPushButton[actionRole="success"] {
    background-color: #12b76a;
    color: #ffffff;
    border-color: #12b76a;
}
QPushButton[actionRole="success"]:hover {
    background-color: #039855;
}
QPushButton[actionRole="danger"] {
    background-color: #ffffff;
    color: #d92d20;
    border: 2px solid #f04438;
}
QPushButton[actionRole="danger"]:hover {
    background-color: #fef3f2;
}
QPushButton:disabled {
    background-color: #d0d5dd;
    color: #667085;
    border-color: #d0d5dd;
}
QLabel#pageTitle {
    font-size: 22px;
    font-weight: 700;
}
QLabel#scanFeedback {
    font-size: 36px;
    font-weight: 700;
    padding: 24px;
    background-color: #ffffff;
    border: 3px solid #84caff;
    border-radius: 12px;
}
QProgressBar {
    border: 1px solid #98a2b3;
    border-radius: 4px;
    background-color: #ffffff;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #12b76a;
}
"""


def register_windows_fonts(font_directory: Path | None = None) -> None:
    """Register installed Windows Chinese fonts for every Qt platform plugin."""
    directory = (
        font_directory
        if font_directory is not None
        else Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    )
    for filename in ("msyh.ttc", "msyhbd.ttc"):
        path = directory / filename
        if path.is_file():
            QFontDatabase.addApplicationFont(str(path))


def light_palette(base: QPalette) -> QPalette:
    """Return a light palette independent of the current Windows theme."""
    palette = QPalette(base)
    palette.setColor(QPalette.ColorRole.Window, QColor("#f8fafc"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#1d2939"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f9fafb"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#1d2939"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#175cd3"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#d1e9ff"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#102a56"))
    return palette


class MainWindow(QMainWindow):
    """Host operator identity and all primary application workflows."""

    SCAN_TAB = 0
    RUNS_TAB = 1
    RECORDS_TAB = 2
    IMPORT_TAB = 4

    def __init__(
        self,
        scan_widget: ScanWidget,
        master_data_widget: QWidget,
        import_widget: QWidget,
        bom_widget: QWidget,
        configuration_widget: QWidget,
        run_widget: QWidget,
        records_widget: QWidget,
        audit_widget: QWidget,
        operator_widget: OperatorSessionWidget,
    ) -> None:
        super().__init__()
        register_windows_fonts()
        self._scan_widget = scan_widget
        self.setWindowTitle("SMT 扫码防错")
        self.resize(1180, 760)
        font = QFont()
        font.setFamilies(("Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI"))
        font.setPointSize(10)
        self.setFont(font)
        self.setPalette(light_palette(self.palette()))
        self.setStyleSheet(APPLICATION_STYLE)
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.addWidget(operator_widget)
        self.tab_widget = QTabWidget()
        pages = (
            (scan_widget, "作业 · 扫码", "现场主作业"),
            (run_widget, "作业 · 生产运行", "运行进度与扫码记录"),
            (records_widget, "作业 · 记录查询", "高级记录查询"),
            (master_data_widget, "配置 · 设备与站位", "基础配置"),
            (import_widget, "配置 · 导入配置", "按步骤导入"),
            (bom_widget, "配置 · BOM", "BOM 生命周期"),
            (configuration_widget, "配置 · 产品配置", "产品配置管理"),
            (audit_widget, "系统 · 审计日志", "系统追溯"),
        )
        for page, label, tooltip in pages:
            index = self.tab_widget.addTab(page, label)
            self.tab_widget.setTabToolTip(index, tooltip)
        tab_bar = self.tab_widget.tabBar()
        for index in range(0, 3):
            tab_bar.setTabTextColor(index, QColor("#175cd3"))
        for index in range(3, 7):
            tab_bar.setTabTextColor(index, QColor("#6941c6"))
        tab_bar.setTabTextColor(7, QColor("#475467"))
        self.tab_widget.currentChanged.connect(self._tab_changed)
        central_layout.addWidget(self.tab_widget, 1)
        self.setCentralWidget(central)
        self._prepare_table_viewports()
        QTimer.singleShot(0, self._prepare_table_viewports)

    @Slot()
    def _prepare_table_viewports(self) -> None:
        """Force opaque light table surfaces after Qt polishes the active tab."""
        for table in self.findChildren(QTableWidget):
            table_palette = light_palette(table.palette())
            table_palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
            table.setPalette(table_palette)
            viewport = table.viewport()
            viewport_palette = light_palette(viewport.palette())
            viewport_palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
            viewport.setPalette(viewport_palette)
            viewport.setBackgroundRole(QPalette.ColorRole.Base)
            viewport.setStyleSheet("background-color: #ffffff; color: #1d2939;")
            viewport.setAutoFillBackground(True)

    @Slot(int)
    def _tab_changed(self, index: int) -> None:
        QTimer.singleShot(0, self._prepare_table_viewports)
        if index == self.SCAN_TAB:
            QTimer.singleShot(0, self._scan_widget.focus_scanner)
