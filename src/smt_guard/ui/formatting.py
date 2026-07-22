"""Shared presentation-only formatting helpers."""

from datetime import datetime


def display_datetime(value: datetime | None) -> str:
    """Format a UI timestamp to minute precision without changing stored data."""
    return "" if value is None else value.strftime("%Y-%m-%d %H:%M")
