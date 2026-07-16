import os
import sqlite3
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from smt_guard.operator import OperatorSession
from smt_guard.sqlite import SqliteAuditRepository, SqliteDatabase, SqliteMasterDataRepository
from smt_guard.ui.master_data import DeviceStationWidget


class DeviceStationWidgetTests(unittest.TestCase):
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
        self.connection = sqlite3.connect(":memory:")
        self.addCleanup(self.connection.close)
        SqliteDatabase(self.connection).initialize()
        self.repository = SqliteMasterDataRepository(self.connection)

    def make_widget(self) -> DeviceStationWidget:
        widget = DeviceStationWidget(self.repository)
        self.addCleanup(widget.close)
        return widget

    def test_adds_trimmed_device_and_refreshes_table(self) -> None:
        widget = self.make_widget()
        self.assertEqual(
            ["全部状态", "启用", "停用"],
            [widget.device_status_filter.itemText(index) for index in range(3)],
        )
        self.assertEqual("启用", widget.enable_device_button.text())
        self.assertEqual("停用", widget.disable_device_button.text())
        self.assertFalse(hasattr(widget, "delete_device_button"))
        self.assertFalse(hasattr(widget, "delete_station_button"))
        self.assertEqual(4, widget.device_table.columnCount())
        self.assertEqual(4, widget.station_table.columnCount())
        self.assertFalse(widget.bulk_group.isVisible())
        self.assertEqual("0 台", widget.device_count_label.text())
        widget.device_code_input.setText(" SMT-01 ")
        widget.device_name_input.setText(" Machine 1 ")
        widget.device_line_input.setText(" Line A ")

        widget.add_device_button.click()

        device = self.repository.get_device("SMT-01")
        table_code = widget.device_table.item(0, 0)
        assert table_code is not None
        self.assertEqual("Machine 1", device.name)
        self.assertTrue(device.enabled)
        self.assertEqual(1, widget.device_table.rowCount())
        self.assertEqual("1 台", widget.device_count_label.text())
        self.assertEqual("SMT-01", table_code.text())
        self.assertFalse(widget.enable_device_button.isEnabled())
        self.assertTrue(widget.disable_device_button.isEnabled())
        self.assertIn("已创建设备", widget.status_label.text())

    def test_shows_duplicate_error_without_blocking_dialog(self) -> None:
        self.repository.add_device("SMT-01", "Machine 1", "Line A")
        widget = self.make_widget()
        widget.device_code_input.setText("SMT-01")
        widget.device_name_input.setText("Duplicate")

        widget.add_device_button.click()

        self.assertIn("Duplicate device code", widget.status_label.text())
        self.assertEqual("error", widget.status_label.property("feedbackState"))

    def test_adds_single_and_bulk_stations_for_selected_device(self) -> None:
        self.repository.add_device("SMT-01", "Machine 1", "Line A")
        widget = self.make_widget()
        widget.station_code_input.setText(" F-01 ")

        widget.add_station_button.click()
        widget.bulk_prefix_input.setText("F-")
        widget.bulk_start_input.setValue(2)
        widget.bulk_end_input.setValue(3)
        widget.bulk_width_input.setValue(2)
        widget.bulk_add_button.click()

        self.assertEqual(
            ["F-01", "F-02", "F-03"],
            [station.code for station in self.repository.list_stations("SMT-01")],
        )
        self.assertEqual(3, widget.station_table.rowCount())
        self.assertEqual("3 个", widget.station_count_label.text())
        self.assertFalse(widget.enable_station_button.isEnabled())
        self.assertTrue(widget.disable_station_button.isEnabled())
        self.assertIn("2 个站位", widget.status_label.text())

    def test_device_selection_refreshes_station_context(self) -> None:
        self.repository.add_device("SMT-01", "Machine 1", "Line A")
        self.repository.add_device("SMT-02", "Machine 2", "Line A")
        self.repository.add_station("SMT-02", "R-01")
        widget = self.make_widget()

        widget.device_table.selectRow(1)
        self.app.processEvents()

        station_code = widget.station_table.item(0, 0)
        assert station_code is not None
        self.assertIn("SMT-02", widget.selected_device_label.text())
        self.assertEqual("R-01", station_code.text())

    def test_disables_entities_without_exposing_delete_actions(self) -> None:
        self.repository.add_device("SMT-01", "Machine 1", "Line A")
        self.repository.add_station("SMT-01", "F-01")
        self.repository.mark_station_referenced("SMT-01", "F-01")
        widget = self.make_widget()

        widget.disable_device_button.click()
        self.assertTrue(widget.enable_device_button.isEnabled())
        self.assertFalse(widget.disable_device_button.isEnabled())
        widget.station_table.selectRow(0)
        widget.disable_station_button.click()

        self.assertFalse(self.repository.is_device_enabled("SMT-01"))
        self.assertFalse(self.repository.is_station_enabled("SMT-01", "F-01"))
        self.assertTrue(widget.enable_station_button.isEnabled())
        self.assertFalse(widget.disable_station_button.isEnabled())
        self.assertEqual(1, widget.station_table.rowCount())

    def test_saving_changes_reenables_disabled_device_and_station(self) -> None:
        self.repository.add_device("SMT-01", "Machine 1", "Line A")
        self.repository.add_station("SMT-01", "F-01")
        widget = self.make_widget()

        widget.disable_device_button.click()
        widget.device_name_input.setText("Machine One")
        widget.update_device_button.click()
        self.assertTrue(self.repository.is_device_enabled("SMT-01"))
        self.assertFalse(widget.enable_device_button.isEnabled())
        self.assertTrue(widget.disable_device_button.isEnabled())

        widget.station_table.selectRow(0)
        widget.disable_station_button.click()
        widget.station_name_input.setText("Front feeder")
        widget.update_station_button.click()
        self.assertTrue(self.repository.get_station("SMT-01", "F-01").enabled)
        self.assertFalse(widget.enable_station_button.isEnabled())
        self.assertTrue(widget.disable_station_button.isEnabled())

    def test_filters_updates_enables_and_archives_with_current_operator(self) -> None:
        self.repository.add_device("SMT-01", "Machine 1", "Line A")
        self.repository.add_station("SMT-01", "F-01")
        session = OperatorSession("ADMIN-UI")
        widget = DeviceStationWidget(
            self.repository, operator_provider=session.require
        )
        self.addCleanup(widget.close)

        widget.device_name_input.setText("Machine One")
        widget.device_line_input.setText("Line B")
        widget.update_device_button.click()
        widget.disable_device_button.click()
        self.assertTrue(widget.enable_device_button.isEnabled())
        widget.enable_device_button.click()
        self.assertFalse(widget.enable_device_button.isEnabled())
        widget.station_name_input.setText("Front feeder")
        widget.update_station_button.click()
        widget.disable_station_button.click()

        self.assertEqual("Machine One", self.repository.get_device("SMT-01").name)
        self.assertEqual("Front feeder", self.repository.get_station("SMT-01", "F-01").name)
        self.assertEqual("停用", widget.station_table.item(0, 2).text())  # type: ignore[union-attr]
        audits = SqliteAuditRepository(self.connection).search(actor="ADMIN-UI")
        self.assertEqual(5, len(audits))

    def test_legacy_archived_entities_can_return_to_use(self) -> None:
        self.repository.add_device("SMT-01", "Machine 1", "Line A")
        self.repository.add_station("SMT-01", "F-01")
        self.repository.archive_device("SMT-01")
        widget = self.make_widget()

        self.assertEqual("停用", widget.device_table.item(0, 3).text())  # type: ignore[union-attr]
        widget.enable_device_button.click()
        widget.station_table.selectRow(0)
        widget.enable_station_button.click()

        self.assertFalse(self.repository.get_device("SMT-01").archived)
        self.assertFalse(self.repository.get_station("SMT-01", "F-01").archived)
        self.assertEqual("启用", widget.device_table.item(0, 3).text())  # type: ignore[union-attr]
        self.assertEqual("启用", widget.station_table.item(0, 2).text())  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
