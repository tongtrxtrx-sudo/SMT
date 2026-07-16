"""Top-level navigation window for SMT Guard."""

import os
from pathlib import Path

from PySide6.QtCore import QDateTime, QTimer, Slot
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from smt_guard.ui.operator import OperatorSessionWidget
from smt_guard.ui.scanning import ScanWidget

APPLICATION_STYLE = """
QWidget {
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
    font-size: 14px;
    color: #1d2939;
    background-color: #f8fafc;
}
QMainWindow, QStackedWidget, QTabWidget, QTabWidget::pane, QTabBar {
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
QFrame#sideNavigation {
    background-color: #f2f4f7;
    border-right: 1px solid #d0d5dd;
}
QLabel#navBrand {
    font-size: 20px;
    font-weight: 700;
    padding: 4px 8px 12px 8px;
}
QLabel#navSection {
    color: #475467;
    font-size: 13px;
    font-weight: 700;
    padding: 12px 10px 4px 10px;
}
QPushButton[navItem="true"] {
    background-color: transparent;
    color: #344054;
    border: 0;
    border-radius: 6px;
    padding: 10px 14px;
    text-align: left;
}
QPushButton[navItem="true"]:hover {
    background-color: #e4e7ec;
}
QPushButton[navItem="true"]:checked {
    background-color: #d1e9ff;
    color: #175cd3;
    font-weight: 700;
}
QFrame#diagnosticBar {
    background-color: #ecfdf3;
    border: 1px solid #abefc6;
    border-radius: 6px;
}
QLabel#diagnosticText {
    color: #067647;
    padding: 6px 10px;
}
QFrame#selectionCard, QFrame#scanHero, QFrame#scanInputCard,
QFrame#historyCard, QFrame#runSummaryCard, QFrame#dropZone {
    background-color: #ffffff;
    border: 1px solid #d0d5dd;
    border-radius: 10px;
}
QFrame#dropZone {
    border: 2px dashed #b2ccff;
    background-color: #f8faff;
}
QLabel#productSummary {
    font-size: 25px;
    font-weight: 700;
}
QLabel#progressCount {
    font-size: 26px;
    font-weight: 700;
}
QLabel[summaryChip="true"] {
    border-radius: 7px;
    padding: 12px 16px;
    font-size: 17px;
    font-weight: 600;
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

    PAGE_NAMES = (
        "扫码作业",
        "生产运行",
        "记录查询",
        "设备与站位",
        "导入配置",
        "BOM 管理",
        "产品配置",
        "审计日志",
    )

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

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.side_navigation = QFrame()
        self.side_navigation.setObjectName("sideNavigation")
        self.side_navigation.setFixedWidth(180)
        navigation_layout = QVBoxLayout(self.side_navigation)
        navigation_layout.setContentsMargins(12, 12, 12, 12)
        navigation_layout.setSpacing(3)
        brand = QLabel("SMT Guard")
        brand.setObjectName("navBrand")
        navigation_layout.addWidget(brand)

        self.navigation_group = QButtonGroup(self)
        self.navigation_group.setExclusive(True)
        self.navigation_buttons: list[QPushButton] = []
        section_starts = {0: "作业", 3: "配置", 7: "系统"}
        tooltips = (
            "现场主作业",
            "运行进度与扫码记录",
            "高级记录查询",
            "基础配置",
            "按步骤导入",
            "BOM 生命周期",
            "产品配置管理",
            "系统追溯",
        )
        for index, name in enumerate(self.PAGE_NAMES):
            if index in section_starts:
                section = QLabel(section_starts[index])
                section.setObjectName("navSection")
                navigation_layout.addWidget(section)
            button = QPushButton(name)
            button.setCheckable(True)
            button.setProperty("navItem", True)
            button.setToolTip(tooltips[index])
            self.navigation_group.addButton(button, index)
            self.navigation_buttons.append(button)
            navigation_layout.addWidget(button)
        navigation_layout.addStretch(1)
        body.addWidget(self.side_navigation)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(14, 10, 14, 10)
        content_layout.setSpacing(8)
        self.page_stack = QStackedWidget()
        # Keep the historical attribute as a compatibility alias for workflow wiring.
        self.tab_widget = self.page_stack
        pages = (
            scan_widget,
            run_widget,
            records_widget,
            master_data_widget,
            import_widget,
            bom_widget,
            configuration_widget,
            audit_widget,
        )
        for page in pages:
            self.page_stack.addWidget(page)
        self.navigation_group.idClicked.connect(self.page_stack.setCurrentIndex)
        self.page_stack.currentChanged.connect(self._tab_changed)
        self.navigation_buttons[0].setChecked(True)
        content_layout.addWidget(self.page_stack, 1)

        self.diagnostic_frame = QFrame()
        self.diagnostic_frame.setObjectName("diagnosticBar")
        diagnostic_layout = QHBoxLayout(self.diagnostic_frame)
        diagnostic_layout.setContentsMargins(0, 0, 0, 0)
        self.diagnostic_label = QLabel()
        self.diagnostic_label.setObjectName("diagnosticText")
        diagnostic_layout.addWidget(self.diagnostic_label)
        content_layout.addWidget(self.diagnostic_frame)
        body.addWidget(content, 1)
        central_layout.addLayout(body, 1)
        self.setCentralWidget(central)
        scan_widget.configuration_combo.currentTextChanged.connect(
            self._update_diagnostics
        )
        scan_widget.run_changed.connect(self._update_diagnostics)
        self._update_diagnostics()
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
        if 0 <= index < len(self.navigation_buttons):
            self.navigation_buttons[index].setChecked(True)
        QTimer.singleShot(0, self._prepare_table_viewports)
        if index == self.SCAN_TAB:
            QTimer.singleShot(0, self._scan_widget.focus_scanner)

    @Slot()
    def _update_diagnostics(self) -> None:
        voice_mode = (
            "SAPI"
            if os.environ.get("SMT_GUARD_VOICE_ENABLED", "1").strip().casefold()
            not in {"0", "false", "no", "off"}
            else "静默"
        )
        configuration = self._scan_widget.configuration_combo.currentText() or "未选择"
        updated_at = QDateTime.currentDateTime().toString("HH:mm")
        self.diagnostic_label.setText(
            f"● 数据库正常  ·  扫码输入：按当前页面自动聚焦  ·  "
            f"中文语音：{voice_mode}  ·  当前配置：{configuration}  ·  "
            f"更新于 {updated_at}"
        )
