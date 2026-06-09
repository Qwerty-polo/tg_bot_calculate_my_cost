"""Helpers for computing period boundaries (day / week / month)."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from app.models.enums import BudgetPeriod


def start_of_day(now: datetime) -> datetime:
    return datetime.combine(now.date(), time.min)


def day_range(now: datetime) -> tuple[datetime, datetime]:
    start = start_of_day(now)
    return start, start + timedelta(days=1)


def week_range(now: datetime) -> tuple[datetime, datetime]:
    """Monday 00:00 to next Monday 00:00."""
    start = start_of_day(now) - timedelta(days=now.weekday())
    return start, start + timedelta(days=7)


def month_range(now: datetime) -> tuple[datetime, datetime]:
    start = datetime(now.year, now.month, 1)
    if now.month == 12:
        end = datetime(now.year + 1, 1, 1)
    else:
        end = datetime(now.year, now.month + 1, 1)
    return start, end


def range_for_period(period: BudgetPeriod, now: datetime) -> tuple[datetime, datetime]:
    if period is BudgetPeriod.WEEK:
        return week_range(now)
    return month_range(now)


def days_elapsed(start: datetime, now: datetime) -> float:
    """Fractional days elapsed since ``start`` (at least a fraction of a day)."""
    delta = (now - start).total_seconds() / 86400.0
    return max(delta, 1e-6)


def total_days(start: datetime, end: datetime) -> float:
    return max((end - start).total_seconds() / 86400.0, 1e-6)
