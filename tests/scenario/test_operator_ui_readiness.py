import os
import unittest
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QTableWidget

from smt_guard.app import ApplicationRuntime, create_runtime
from smt_guard.feedback import FeedbackTone
from smt_guard.scan import ProductConfiguration


class SilentAudio:
    def emit(self, tone: FeedbackTone) -> None:
        del tone


class OperatorUiReadinessTests(unittest.TestCase):
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
        self.runtime: ApplicationRuntime = create_runtime(
            Path(temporary.name),
            audio=SilentAudio(),
            clock=lambda: datetime(2026, 7, 11, 12, 0, tzinfo=UTC),
            run_id_factory=lambda: "RUN-FOCUS",
        )
        self.addCleanup(self.runtime.close)
        self.runtime.operator_session.sign_in("OP-FOCUS")
        self.runtime.master_data.add_device("SMT-01", "Machine 1", "Line A")
        self.runtime.master_data.add_station("SMT-01", "F-01")
        self.runtime.configurations.save(
            ProductConfiguration(
                "501000087", "V1", {("SMT-01", "F-01"): "013000081"}
            )
        )
        self.runtime.scan_widget.refresh_configurations()
        self.runtime.window.show()
        self.app.processEvents()

    def test_applies_chinese_capable_explicit_light_theme(self) -> None:
        style = self.runtime.window.styleSheet()

        self.assertIn("Microsoft YaHei UI", style)
        self.assertIn("color: #1d2939", style)
        self.assertIn("QTableWidget", style)
        self.assertIn("background-color: #ffffff", style)

    def test_registers_windows_yahei_font_for_headless_rendering(self) -> None:
        self.assertIn("Microsoft YaHei UI", QFontDatabase.families())

    def test_table_viewports_fill_with_light_background(self) -> None:
        visible_indexes = [
            index
            for index, button in enumerate(self.runtime.window.navigation_buttons)
            if not button.isHidden()
        ]
        for index in visible_indexes:
            self.runtime.window.tab_widget.setCurrentIndex(index)
            self.app.processEvents()
            page = self.runtime.window.tab_widget.widget(index)
            if page is None:
                self.fail(f"Missing tab page at index {index}")
            tables = page.findChildren(QTableWidget)
            self.assertTrue(tables)
            for table in tables:
                with self.subTest(tab=index, table=type(table.parent()).__name__):
                    viewport = table.viewport()
                    self.assertTrue(viewport.autoFillBackground())
                    self.assertEqual(
                        viewport.palette().color(viewport.backgroundRole()).name(),
                        "#ffffff",
                    )

    def test_starting_run_focuses_scanner_input(self) -> None:
        self.runtime.scan_widget.start_button.click()
        self.app.processEvents()

        self.assertTrue(self.runtime.scan_widget.scan_input.hasFocus())

    def test_returning_to_scan_tab_restores_scanner_focus(self) -> None:
        self.runtime.scan_widget.start_button.click()
        self.runtime.window.tab_widget.setCurrentIndex(1)
        self.app.processEvents()
        self.runtime.window.tab_widget.setCurrentIndex(0)
        self.app.processEvents()

        self.assertTrue(self.runtime.scan_widget.scan_input.hasFocus())


if __name__ == "__main__":
    unittest.main()
