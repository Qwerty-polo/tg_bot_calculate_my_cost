from datetime import datetime

from app.analytics.insights import (
    detect_subscriptions,
    detect_unusual_expenses,
    forecast_overspend_days,
)
from app.models import Expense, ExpenseCategory


def _expense(amount, merchant=None, category=ExpenseCategory.OTHER, currency="UAH"):
    return Expense(
        amount=amount,
        merchant=merchant,
        category=category,
        currency=currency,
        occurred_at=datetime(2026, 1, 1),
    )


def test_forecast_overspend_returns_none_without_budget():
    start = datetime(2026, 1, 1)
    now = datetime(2026, 1, 2)
    end = datetime(2026, 1, 8)
    assert forecast_overspend_days(100, 0, start, now, end) is None


def test_forecast_overspend_predicts_days():
    start = datetime(2026, 1, 1)
    now = datetime(2026, 1, 3)  # 2 days elapsed
    end = datetime(2026, 1, 8)
    # Spent 4000 in 2 days => 2000/day. Budget 5000 => 1000 remaining => 0.5 days.
    days = forecast_overspend_days(4000, 5000, start, now, end)
    assert days == 0


def test_forecast_no_overspend_when_pace_is_safe():
    start = datetime(2026, 1, 1)
    now = datetime(2026, 1, 4)  # 3 days
    end = datetime(2026, 1, 8)
    # Spent 300 in 3 days => 100/day; 4 days left => 400 more, budget 5000. Safe.
    assert forecast_overspend_days(300, 5000, start, now, end) is None


def test_detect_subscriptions_groups_repeated_merchant_amount():
    expenses = [
        _expense(199, "Netflix"),
        _expense(199, "Netflix"),
        _expense(50, "Coffee"),
    ]
    subs = detect_subscriptions(expenses)
    assert len(subs) == 1
    assert subs[0]["merchant"] == "Netflix"
    assert subs[0]["count"] == 2


def test_detect_unusual_expenses_flags_outlier():
    expenses = [_expense(x) for x in (50, 60, 55, 65, 2000)]
    unusual = detect_unusual_expenses(expenses)
    assert unusual
    assert unusual[0]["amount"] == 2000
