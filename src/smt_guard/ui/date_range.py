"""Reusable date-time range controls for management queries."""

from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta

from PySide6.QtCore import QDate, QDateTime, QTime, Signal
from PySide6.QtWidgets import QDateTimeEdit, QHBoxLayout, QLabel, QPushButton, QWidget


class DateRangeFilter(QWidget):
    """Present an editable date range with common shop-floor query shortcuts."""

    range_selected = Signal()

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        default_days: int = 7,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._clock = clock or (lambda: datetime.now(UTC))
        now = self._clock()
        self._timezone = now.tzinfo

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("开始时间"))
        self.started_from_input = self._create_editor()
        layout.addWidget(self.started_from_input)
        layout.addWidget(QLabel("至"))
        self.started_to_input = self._create_editor()
        layout.addWidget(self.started_to_input)
        layout.addSpacing(8)

        self.today_button = QPushButton("今天")
        self.seven_days_button = QPushButton("近 7 天")
        self.thirty_days_button = QPushButton("近 30 天")
        for button in (
            self.today_button,
            self.seven_days_button,
            self.thirty_days_button,
        ):
            button.setProperty("actionRole", "secondary")
            layout.addWidget(button)
        layout.addStretch(1)

        self.today_button.clicked.connect(lambda: self.set_recent_days(1))
        self.seven_days_button.clicked.connect(lambda: self.set_recent_days(7))
        self.thirty_days_button.clicked.connect(lambda: self.set_recent_days(30))
        self.set_recent_days(default_days, emit_signal=False)

    @staticmethod
    def _create_editor() -> QDateTimeEdit:
        editor = QDateTimeEdit()
        editor.setCalendarPopup(True)
        editor.setDisplayFormat("yyyy-MM-dd HH:mm")
        editor.setToolTip("可直接输入，也可打开日历选择日期和时间")
        return editor

    def set_recent_days(self, days: int, *, emit_signal: bool = True) -> None:
        """Set a whole-day range ending today and optionally request a query."""
        if days < 1:
            raise ValueError("Date range must include at least one day")
        now = self._clock()
        start_date = now.date() - timedelta(days=days - 1)
        started_from = datetime.combine(start_date, time.min, tzinfo=now.tzinfo)
        started_to = datetime.combine(now.date(), time.max, tzinfo=now.tzinfo)
        self.started_from_input.setDateTime(self._to_qdatetime(started_from))
        self.started_to_input.setDateTime(self._to_qdatetime(started_to))
        if emit_signal:
            self.range_selected.emit()

    def values(self) -> tuple[datetime, datetime]:
        """Return Python datetimes using the application's clock timezone."""
        return (
            self._to_datetime(self.started_from_input.dateTime()),
            self._to_datetime(self.started_to_input.dateTime()),
        )

    @staticmethod
    def _to_qdatetime(value: datetime) -> QDateTime:
        return QDateTime(
            QDate(value.year, value.month, value.day),
            QTime(value.hour, value.minute, value.second, value.microsecond // 1000),
        )

    def _to_datetime(self, value: QDateTime) -> datetime:
        date = value.date()
        clock_time = value.time()
        return datetime(
            date.year(),
            date.month(),
            date.day(),
            clock_time.hour(),
            clock_time.minute(),
            clock_time.second(),
            clock_time.msec() * 1000,
            tzinfo=self._timezone,
        )
