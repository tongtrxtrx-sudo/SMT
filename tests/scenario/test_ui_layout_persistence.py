import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from smt_guard.ui.tables import (
    UiLayoutStore,
    enable_splitter_layout,
    enable_table_layout,
    set_column_widths,
    set_responsive_columns,
)


class UiLayoutPersistenceTests(unittest.TestCase):
    app: QApplication

    @classmethod
    def setUpClass(cls) -> None:
        application = QApplication.instance()
        if application is None:
            cls.app = QApplication([])
        elif isinstance(application, QApplication):
            cls.app = application
        else:
            raise RuntimeError("A non-GUI Qt application already exists")

    def setUp(self) -> None:
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.settings_path = Path(temporary.name) / "ui_layout.json"

    def _table(self, store: UiLayoutStore) -> QTableWidget:
        table = QTableWidget(0, 3)
        self.addCleanup(table.close)
        table.setHorizontalHeaderLabels(("第一列", "第二列", "第三列"))
        set_column_widths(table, (120, 150, 180))
        set_responsive_columns(table, stretch=(0, 1, 2))
        enable_table_layout(table, "test/table", store)
        table.resize(640, 320)
        table.show()
        QTest.qWait(30)
        return table

    def test_table_column_order_and_width_survive_restart(self) -> None:
        table = self._table(UiLayoutStore(self.settings_path))
        header = table.horizontalHeader()
        header.moveSection(header.visualIndex(0), 2)
        header.resizeSection(1, 240)
        QTest.qWait(320)

        restored = self._table(UiLayoutStore(self.settings_path))
        restored_header = restored.horizontalHeader()
        self.assertEqual(2, restored_header.visualIndex(0))
        self.assertEqual(240, restored_header.sectionSize(1))

    def test_splitter_ratio_survives_restart(self) -> None:
        store = UiLayoutStore(self.settings_path)
        splitter = QSplitter()
        self.addCleanup(splitter.close)
        splitter.addWidget(QWidget())
        splitter.addWidget(QWidget())
        splitter.setChildrenCollapsible(False)
        enable_splitter_layout(splitter, "test/splitter", store)
        splitter.resize(640, 320)
        splitter.show()
        QTest.qWait(30)
        splitter.moveSplitter(220, 1)
        QTest.qWait(320)

        restored = QSplitter()
        self.addCleanup(restored.close)
        restored.addWidget(QWidget())
        restored.addWidget(QWidget())
        enable_splitter_layout(
            restored,
            "test/splitter",
            UiLayoutStore(self.settings_path),
        )
        restored.resize(640, 320)
        restored.show()
        QTest.qWait(30)
        self.assertAlmostEqual(220, restored.sizes()[0], delta=8)

    def test_clicking_a_truncated_cell_shows_its_complete_value(self) -> None:
        table = self._table(UiLayoutStore(self.settings_path))
        complete_value = "这是需要完整显示的超长字段" * 20
        table.setRowCount(1)
        table.setItem(0, 0, QTableWidgetItem(complete_value))
        table.setColumnWidth(0, 60)
        self.app.processEvents()

        with patch("smt_guard.ui.tables.QToolTip.showText") as show_text:
            QTest.mouseClick(
                table.viewport(),
                Qt.MouseButton.LeftButton,
                pos=table.visualRect(table.model().index(0, 0)).center(),
            )

        show_text.assert_called_once()
        self.assertIn(complete_value, show_text.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
