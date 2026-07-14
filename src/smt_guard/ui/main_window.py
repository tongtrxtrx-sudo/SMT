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
QLineEdit, QSpinBox, QComboBox, QTableWidget {
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
    background-color: #175cd3;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 7px 14px;
}
QPushButton:hover {
    background-color: #1849a9;
}
QPushButton:disabled {
    background-color: #d0d5dd;
    color: #667085;
}
QLabel#pageTitle {
    font-size: 22px;
    font-weight: 700;
}
QLabel#scanFeedback {
    font-size: 28px;
    font-weight: 700;
    padding: 10px;
    background-color: #ffffff;
    border: 1px solid #d0d5dd;
    border-radius: 6px;
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
        self.tab_widget.addTab(scan_widget, "扫码")
        self.tab_widget.addTab(master_data_widget, "设备与站位")
        self.tab_widget.addTab(import_widget, "导入配置")
        self.tab_widget.addTab(bom_widget, "BOM 管理")
        self.tab_widget.addTab(configuration_widget, "产品配置")
        self.tab_widget.addTab(run_widget, "生产运行")
        self.tab_widget.addTab(records_widget, "记录查询")
        self.tab_widget.addTab(audit_widget, "审计日志")
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
        if index == 0:
            QTimer.singleShot(0, self._scan_widget.focus_scanner)
