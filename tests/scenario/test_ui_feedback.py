import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox

from smt_guard.ui.components import confirm_action, show_notification


class UiFeedbackTests(unittest.TestCase):
    app: QApplication

    @classmethod
    def setUpClass(cls) -> None:
        application = QApplication.instance()
        cls.app = application if isinstance(application, QApplication) else QApplication([])

    def test_notification_disappears_after_timeout(self) -> None:
        label = QLabel()
        label.show()

        show_notification(label, "success", "保存成功", duration_ms=20)
        self.assertTrue(label.isVisible())
        self.assertEqual("保存成功", label.text())

        QTest.qWait(35)
        self.assertFalse(label.isVisible())

    def test_latest_notification_is_not_hidden_by_an_older_timer(self) -> None:
        label = QLabel()
        label.show()
        show_notification(label, "success", "第一次", duration_ms=20)
        QTest.qWait(10)
        show_notification(label, "error", "第二次", duration_ms=60)

        QTest.qWait(20)
        self.assertTrue(label.isVisible())
        self.assertEqual("第二次", label.text())
        QTest.qWait(50)
        self.assertFalse(label.isVisible())

    def test_confirmation_only_accepts_explicit_yes(self) -> None:
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            self.assertFalse(confirm_action(None, "停用配置", "确认停用 501/001？"))
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            self.assertTrue(confirm_action(None, "停用配置", "确认停用 501/001？"))


if __name__ == "__main__":
    unittest.main()
