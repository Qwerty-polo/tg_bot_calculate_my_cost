"""Analytics orchestration: turns DB rows into a metrics dictionary.

The resulting metrics dict is consumed both by the deterministic formatter and
by the AI to generate natural-language insights.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.analytics.insights import (
    detect_subscriptions,
    detect_unusual_expenses,
    forecast_overspend_days,
)
from app.models import BudgetPeriod, User
from app.services.budget_service import BudgetService
from app.services.expense_service import ExpenseService
from app.utils.timeframe import (
    days_elapsed,
    range_for_period,
)


class AnalyticsService:
    def __init__(
        self,
        expense_service: ExpenseService,
        budget_service: BudgetService,
    ) -> None:
        self.expenses = expense_service
        self.budgets = budget_service

    async def build_metrics(
        self,
        user: User,
        period: BudgetPeriod,
        now: datetime | None = None,
    ) -> dict:
        now = now or datetime.utcnow()
        start, end = range_for_period(period, now)

        total = await self.expenses.total_in_range(user.id, start, end)
        by_category = await self.expenses.totals_by_category(user.id, start, end)
        biggest = await self.expenses.biggest_expense(user.id, start, end)
        items = await self.expenses.list_in_range(user.id, start, end)
        budget = await self.budgets.get_budget(user.id, period)

        currency = budget.currency if budget else user.currency

        categories = [
            {
                "name": cat.title,
                "key": cat.value,
                "emoji": cat.emoji,
                "amount": round(amount, 2),
                "pct": round(amount / total * 100, 1) if total else 0.0,
            }
            for cat, amount in by_category.items()
        ]

        metrics: dict = {
            "period": period.value,
            "currency": currency,
            "total_spent": round(total, 2),
            "expense_count": len(items),
            "categories": categories,
            "top_category": categories[0] if categories else None,
            "daily_average": round(total / days_elapsed(start, now), 2) if total else 0.0,
            "subscriptions": detect_subscriptions(items),
            "unusual_expenses": detect_unusual_expenses(items),
        }

        if biggest is not None:
            metrics["biggest_expense"] = {
                "merchant": biggest.merchant,
                "amount": round(float(biggest.amount), 2),
                "currency": biggest.currency,
                "category": biggest.category.value,
                "datetime": biggest.occurred_at.isoformat(),
            }

        if budget is not None:
            budget_amount = round(float(budget.amount), 2)
            metrics["budget"] = budget_amount
            metrics["budget_used_pct"] = (
                round(total / budget_amount * 100, 1) if budget_amount else 0.0
            )
            metrics["budget_remaining"] = round(budget_amount - total, 2)
            metrics["days_until_overspend"] = forecast_overspend_days(
                total, budget_amount, start, now, end
            )

        if period is BudgetPeriod.WEEK:
            prev_start = start - timedelta(days=7)
            prev_total = await self.expenses.total_in_range(user.id, prev_start, start)
            metrics["previous_period_total"] = round(prev_total, 2)
            if prev_total > 0:
                metrics["change_vs_previous_pct"] = round(
                    (total - prev_total) / prev_total * 100, 1
                )

        return metrics
