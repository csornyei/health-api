import os
from datetime import date

os.environ.setdefault("INFLUXDB_HOST", "http://localhost:8181")
os.environ.setdefault("INFLUXDB_TOKEN", "test-token")
os.environ.setdefault("INFLUXDB_DATABASE", "test-db")
os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

from src.routers.summary import SummaryType, _compute_period


def test_compute_period_week() -> None:
    assert _compute_period(date(2026, 7, 15), SummaryType.week) == (
        date(2026, 7, 9),
        date(2026, 7, 15),
    )


def test_compute_period_twoweeks() -> None:
    assert _compute_period(date(2026, 7, 15), SummaryType.twoweeks) == (
        date(2026, 7, 2),
        date(2026, 7, 15),
    )


def test_compute_period_thirtydays() -> None:
    assert _compute_period(date(2026, 7, 15), SummaryType.thirtydays) == (
        date(2026, 6, 16),
        date(2026, 7, 15),
    )


def test_compute_period_month_uses_whole_calendar_month() -> None:
    assert _compute_period(date(2026, 7, 15), SummaryType.month) == (
        date(2026, 7, 1),
        date(2026, 7, 31),
    )
