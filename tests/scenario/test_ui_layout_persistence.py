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
    reset_persistent_layouts,
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

    def _table(
        self,
        store: UiLayoutStore,
        *,
        width: int = 640,
        narrow_hidden: tuple[int, ...] = (),
        narrow_threshold: int = 0,
    ) -> QTableWidget:
        table = QTableWidget(0, 3)
        self.addCleanup(table.close)
        table.setHorizontalHeaderLabels(("第一列", "第二列", "第三列"))
        set_column_widths(table, (120, 150, 180))
        set_responsive_columns(table, stretch=(0, 1, 2))
        enable_table_layout(
            table,
            "test/table",
            store,
            narrow_hidden=narrow_hidden,
            narrow_threshold=narrow_threshold,
        )
        table.resize(width, 320)
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

    def test_splitter_ratio_is_scaled_when_restored_at_a_narrower_width(self) -> None:
        store = UiLayoutStore(self.settings_path)
        splitter = QSplitter()
        self.addCleanup(splitter.close)
        splitter.addWidget(QWidget())
        splitter.addWidget(QWidget())
        enable_splitter_layout(splitter, "test/cross-screen", store)
        splitter.resize(1000, 320)
        splitter.show()
        QTest.qWait(30)
        splitter.moveSplitter(400, 1)
        QTest.qWait(320)

        restored = QSplitter()
        self.addCleanup(restored.close)
        restored.addWidget(QWidget())
        restored.addWidget(QWidget())
        enable_splitter_layout(
            restored,
            "test/cross-screen",
            UiLayoutStore(self.settings_path),
        )
        restored.resize(500, 320)
        restored.show()
        QTest.qWait(30)

        self.assertAlmostEqual(200, restored.sizes()[0], delta=10)

    def test_table_widths_are_adapted_when_restored_on_a_narrower_screen(self) -> None:
        table = self._table(UiLayoutStore(self.settings_path), width=1000)
        table.horizontalHeader().resizeSection(0, 360)
        QTest.qWait(320)

        restored = self._table(UiLayoutStore(self.settings_path), width=500)
        visible_width = sum(
            restored.columnWidth(column)
            for column in range(restored.columnCount())
            if not restored.isColumnHidden(column)
        )

        self.assertLess(restored.columnWidth(0), 360)
        self.assertLessEqual(visible_width, restored.viewport().width() + 4)

    def test_narrow_columns_toggle_when_the_viewport_crosses_the_breakpoint(self) -> None:
        table = self._table(
            UiLayoutStore(self.settings_path),
            width=520,
            narrow_hidden=(1,),
            narrow_threshold=600,
        )
        self.assertTrue(table.isColumnHidden(1))

        table.resize(800, 320)
        self.app.processEvents()

        self.assertFalse(table.isColumnHidden(1))

    def test_visible_columns_refill_width_when_resized_within_same_breakpoint(self) -> None:
        table = self._table(
            UiLayoutStore(self.settings_path),
            width=500,
            narrow_hidden=(1,),
            narrow_threshold=700,
        )
        table.resize(620, 320)
        self.app.processEvents()
        QTest.qWait(20)

        visible_width = sum(
            table.columnWidth(column)
            for column in range(table.columnCount())
            if not table.isColumnHidden(column)
        )

        self.assertGreaterEqual(visible_width, table.viewport().width() - 8)

    def test_narrow_columns_leave_no_blank_bands_after_narrow_state_restore(self) -> None:
        store = UiLayoutStore(self.settings_path)
        narrow = self._table(
            store,
            width=520,
            narrow_hidden=(1,),
            narrow_threshold=700,
        )
        narrow.horizontalHeader().resizeSection(0, 180)
        QTest.qWait(320)

        restored = self._table(
            UiLayoutStore(self.settings_path),
            width=520,
            narrow_hidden=(1,),
            narrow_threshold=700,
        )
        visible = sorted(
            (
                restored.horizontalHeader().visualIndex(column),
                restored.columnViewportPosition(column),
                restored.columnWidth(column),
            )
            for column in range(restored.columnCount())
            if not restored.isColumnHidden(column)
        )

        expected_position = 0
        for _visual_index, position, width in visible:
            self.assertAlmostEqual(expected_position, position, delta=2)
            expected_position += width

    def test_reset_restores_defaults_and_clears_saved_states(self) -> None:
        store = UiLayoutStore(self.settings_path)
        root = QWidget()
        self.addCleanup(root.close)
        table = self._table(store)
        table.setParent(root)
        root.resize(640, 320)
        table.resize(640, 320)
        root.show()
        self.app.processEvents()
        header = table.horizontalHeader()
        header.moveSection(header.visualIndex(0), 2)
        header.resizeSection(1, 240)
        QTest.qWait(320)

        reset_persistent_layouts(root, store)

        self.assertEqual(0, header.visualIndex(0))
        self.assertNotEqual(240, header.sectionSize(1))
        payload = self.settings_path.read_text(encoding="utf-8")
        self.assertIn('"states": {}', payload)
        self.assertIn('"extents": {}', payload)

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
