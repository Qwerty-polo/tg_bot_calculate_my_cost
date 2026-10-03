"""Local calendar boundaries and UTC storage conversions."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "Europe/Kyiv"


def as_utc(value: datetime, naive_timezone: str = "UTC") -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo(naive_timezone))
    return value.astimezone(UTC).replace(tzinfo=None)


def local_datetime(value: datetime, timezone: str = DEFAULT_TIMEZONE) -> datetime:
    return as_utc(value).replace(tzinfo=UTC).astimezone(ZoneInfo(timezone))


def start_of_day(now: datetime, timezone: str = DEFAULT_TIMEZONE) -> datetime:
    local = local_datetime(now, timezone)
    return datetime.combine(local.date(), time.min, tzinfo=ZoneInfo(timezone))


def day_range(now: datetime, timezone: str = DEFAULT_TIMEZONE) -> tuple[datetime, datetime]:
    start = start_of_day(now, timezone)
    return as_utc(start), as_utc(start + timedelta(days=1))


def week_range(now: datetime, timezone: str = DEFAULT_TIMEZONE) -> tuple[datetime, datetime]:
    """Monday 00:00 to next Monday 00:00."""
    start = start_of_day(now, timezone) - timedelta(days=local_datetime(now, timezone).weekday())
    return as_utc(start), as_utc(start + timedelta(days=7))


def month_range(now: datetime, timezone: str = DEFAULT_TIMEZONE) -> tuple[datetime, datetime]:
    local = local_datetime(now, timezone)
    start = datetime(local.year, local.month, 1, tzinfo=ZoneInfo(timezone))
    if local.month == 12:
        end = start.replace(year=local.year + 1, month=1)
    else:
        end = start.replace(month=local.month + 1)
    return as_utc(start), as_utc(end)
