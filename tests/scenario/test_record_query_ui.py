import csv
import os
import unittest
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from smt_guard.exporter import CsvRecordExporter
from smt_guard.feedback import VoicePrompt
from smt_guard.records import Attempt, InMemoryAttemptRepository
from smt_guard.ui.records import RecordQueryWidget
from smt_guard.verification import VerificationResult


def make_attempt(run_id: str, station_code: str) -> Attempt:
    return Attempt(
        id=None,
        timestamp=datetime(2026, 7, 11, 12, 0, tzinfo=UTC),
        run_id=run_id,
        product_code="501000087",
        product_version="V1",
        device_code="SMT-01",
        station_code=station_code,
        expected_material="013000081",
        scanned_material="013000081",
        result=VerificationResult.OK,
        repeated=False,
    )


class FakeAnnouncementSink:
    def __init__(self) -> None:
        self.prompts: list[VoicePrompt] = []

    def announce(self, prompt: VoicePrompt) -> None:
        self.prompts.append(prompt)


class RecordQueryWidgetTests(unittest.TestCase):
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
        self.repository = InMemoryAttemptRepository()
        self.repository.append(make_attempt("RUN-1", "F-01"))
        self.repository.append(make_attempt("RUN-1", "F-02"))
        self.repository.append(make_attempt("RUN-2", "R-01"))
        self.announcements = FakeAnnouncementSink()
        self.widget = RecordQueryWidget(
            self.repository,
            CsvRecordExporter(self.repository),
            announcer=self.announcements,
        )
        self.addCleanup(self.widget.close)

    def test_queries_one_run_in_identifier_order(self) -> None:
        self.widget.run_id_input.setText(" RUN-1 ")

        self.widget.query_button.click()

        self.assertEqual(2, self.widget.record_table.rowCount())
        first_id = self.widget.record_table.item(0, 0)
        second_id = self.widget.record_table.item(1, 0)
        assert first_id is not None and second_id is not None
        self.assertEqual(["1", "2"], [first_id.text(), second_id.text()])
        run_id = self.widget.record_table.item(0, 2)
        assert run_id is not None
        self.assertEqual("RUN-1", run_id.toolTip())
        self.assertTrue(self.widget.record_table.isColumnHidden(2))
        self.assertEqual(
            [1, 5, 6, 7, 8, 9, 10],
            [
                column
                for column in range(self.widget.record_table.columnCount())
                if not self.widget.record_table.isColumnHidden(column)
            ],
        )
        self.widget.resize(980, 700)
        self.widget.show()
        self.app.processEvents()
        self.assertEqual(0, self.widget.record_table.horizontalScrollBar().maximum())
        self.assertEqual(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
            self.widget.record_table.horizontalScrollBarPolicy(),
        )
        self.assertIn("RUN-1", self.widget.result_title.text())
        self.assertEqual("2 条", self.widget.total_chip.text())
        self.assertIn("2 条", self.widget.status_label.text())

    def test_shows_clear_empty_result(self) -> None:
        self.widget.run_id_input.setText("EMPTY")

        self.widget.query_button.click()

        self.assertEqual(0, self.widget.record_table.rowCount())
        self.assertIn("未找到", self.widget.status_label.text())
        self.assertIn("没有扫码记录", self.widget.empty_state.title_label.text())

    def test_exports_only_selected_run_to_temporary_csv(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "records.csv"
            self.widget.run_id_input.setText("RUN-1")
            self.widget.export_path_input.setText(str(path))

            self.widget.export_button.click()

            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))

        self.assertEqual(2, len(rows))
        self.assertEqual({"RUN-1"}, {row["内部运行编号"] for row in rows})
        self.assertIn("导出", self.widget.status_label.text())
        self.assertEqual([VoicePrompt.RECORDS_EXPORTED], self.announcements.prompts)

    def test_export_failure_announces_fixed_failure_prompt(self) -> None:
        self.widget.run_id_input.setText("RUN-1")
        self.widget.export_path_input.clear()

        self.widget.export_button.click()

        self.assertEqual([VoicePrompt.EXPORT_FAILED], self.announcements.prompts)
        self.assertIn("导出路径", self.widget.status_label.text())


if __name__ == "__main__":
    unittest.main()
