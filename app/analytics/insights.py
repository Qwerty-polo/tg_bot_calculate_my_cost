"""Pure analytics helpers (no DB / no I/O) so they are easy to unit test."""

from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime

from app.models import Expense


def forecast_overspend_days(
    spent: float,
    budget: float,
    start: datetime,
    now: datetime,
    end: datetime,
) -> int | None:
    """Estimate days until the budget is exhausted at the current pace.

    Returns ``None`` when there is no budget, nothing spent yet, or the pace
    will not exceed the budget before the period ends.
    """
    if budget <= 0 or spent <= 0:
        return None
    elapsed_days = max((now - start).total_seconds() / 86400.0, 1e-6)
    pace = spent / elapsed_days  # spend per day
    if pace <= 0:
        return None
    remaining_budget = budget - spent
    if remaining_budget <= 0:
        return 0
    days_to_exhaust = remaining_budget / pace
    days_left_in_period = (end - now).total_seconds() / 86400.0
    if days_to_exhaust >= days_left_in_period:
        return None
    return max(int(days_to_exhaust), 0)


def detect_subscriptions(
    expenses: Sequence[Expense], *, min_occurrences: int = 2
) -> list[dict]:
    """Detect likely recurring subscriptions by repeated merchant + amount.

    A subscription is a (merchant, amount) pair that appears at least
    ``min_occurrences`` times.
    """
    groups: dict[tuple[str, float], list[Expense]] = defaultdict(list)
    for expense in expenses:
        if not expense.merchant:
            continue
        key = (expense.merchant.strip().lower(), round(float(expense.amount), 2))
        groups[key].append(expense)

    subscriptions: list[dict] = []
    for (_merchant, amount), items in groups.items():
        if len(items) >= min_occurrences:
            subscriptions.append(
                {
                    "merchant": items[0].merchant,
                    "amount": amount,
                    "currency": items[0].currency,
                    "count": len(items),
                }
            )
    subscriptions.sort(key=lambda s: s["amount"] * s["count"], reverse=True)
    return subscriptions


def detect_unusual_expenses(
    expenses: Sequence[Expense], *, threshold: float = 3.0
) -> list[dict]:
    """Flag expenses whose amount is far above the typical spend.

    Uses a robust ``median + threshold * (1.4826 * MAD)`` cutoff (MAD = median
    absolute deviation). This is resistant to a single large outlier inflating
    the threshold, unlike a mean/stdev approach. Falls back to ``> 3x median``
    when the MAD is zero (many identical amounts).
    """
    amounts = [float(e.amount) for e in expenses]
    if len(amounts) < 3:
        return []
    median = statistics.median(amounts)
    mad = statistics.median([abs(a - median) for a in amounts])
    if mad > 0:
        cutoff = median + threshold * 1.4826 * mad
    else:
        cutoff = median * 3
    unusual = [
        {
            "merchant": e.merchant,
            "amount": float(e.amount),
            "currency": e.currency,
            "category": e.category.value,
        }
        for e in expenses
        if float(e.amount) >= cutoff and float(e.amount) > median
    ]
    unusual.sort(key=lambda x: x["amount"], reverse=True)
    return unusual
