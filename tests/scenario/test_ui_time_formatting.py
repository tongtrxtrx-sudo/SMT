import unittest
from datetime import UTC, datetime

from smt_guard.ui.formatting import display_datetime


class UiTimeFormattingTests(unittest.TestCase):
    def test_display_uses_minute_precision_without_mutating_source(self) -> None:
        source = datetime(2026, 7, 16, 15, 19, 58, 654321, tzinfo=UTC)

        self.assertEqual("2026-07-16 15:19", display_datetime(source))
        self.assertEqual((58, 654321), (source.second, source.microsecond))

    def test_optional_time_displays_as_blank(self) -> None:
        self.assertEqual("", display_datetime(None))


if __name__ == "__main__":
    unittest.main()
