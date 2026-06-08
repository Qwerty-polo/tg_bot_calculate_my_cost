"""Expense persistence and aggregation queries."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.schemas import ParsedExpense
from app.models import Expense, ExpenseCategory


class ExpenseService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_many(
        self,
        user_id: int,
        parsed: list[ParsedExpense],
        *,
        default_currency: str,
        raw_text: str | None = None,
        fallback_dt: datetime | None = None,
    ) -> list[Expense]:
        """Persist a batch of parsed expenses for a user."""
        fallback_dt = fallback_dt or datetime.utcnow()
        created: list[Expense] = []
        for item in parsed:
            expense = Expense(
                user_id=user_id,
                amount=item.amount,
                currency=item.currency or default_currency,
                occurred_at=item.occurred_at or fallback_dt,
                merchant=item.merchant,
                category=item.category,
                description=item.description,
                raw_text=raw_text,
            )
            self.session.add(expense)
            created.append(expense)
        await self.session.flush()
        return created

    async def list_in_range(
        self, user_id: int, start: datetime, end: datetime
    ) -> list[Expense]:
        result = await self.session.execute(
            select(Expense)
            .where(
                Expense.user_id == user_id,
                Expense.occurred_at >= start,
                Expense.occurred_at < end,
            )
            .order_by(Expense.occurred_at.desc())
        )
        return list(result.scalars().all())

    async def total_in_range(
        self, user_id: int, start: datetime, end: datetime
    ) -> float:
        result = await self.session.execute(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(
                Expense.user_id == user_id,
                Expense.occurred_at >= start,
                Expense.occurred_at < end,
            )
        )
        return float(result.scalar_one())

    async def totals_by_category(
        self, user_id: int, start: datetime, end: datetime
    ) -> dict[ExpenseCategory, float]:
        result = await self.session.execute(
            select(Expense.category, func.sum(Expense.amount))
            .where(
                Expense.user_id == user_id,
                Expense.occurred_at >= start,
                Expense.occurred_at < end,
            )
            .group_by(Expense.category)
            .order_by(func.sum(Expense.amount).desc())
        )
        return {category: float(total) for category, total in result.all()}

    async def biggest_expense(
        self, user_id: int, start: datetime, end: datetime
    ) -> Expense | None:
        result = await self.session.execute(
            select(Expense)
            .where(
                Expense.user_id == user_id,
                Expense.occurred_at >= start,
                Expense.occurred_at < end,
            )
            .order_by(Expense.amount.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def daily_totals(
        self, user_id: int, start: datetime, end: datetime
    ) -> dict[str, float]:
        """Sum of expenses per calendar day (YYYY-MM-DD) within the range."""
        day = func.strftime("%Y-%m-%d", Expense.occurred_at)
        result = await self.session.execute(
            select(day, func.sum(Expense.amount))
            .where(
                Expense.user_id == user_id,
                Expense.occurred_at >= start,
                Expense.occurred_at < end,
            )
            .group_by(day)
            .order_by(day)
        )
        return {str(d): float(total) for d, total in result.all()}
