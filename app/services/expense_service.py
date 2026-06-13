"""Expense persistence and aggregation queries."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import looks_like_income
from app.ai.schemas import ParsedExpense
from app.config import CURRENCY_CODE
from app.models import Expense


class ExpenseService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_many(
        self,
        user_id: int,
        parsed: list[ParsedExpense],
        *,
        raw_text: str | None = None,
        fallback_dt: datetime | None = None,
    ) -> list[Expense]:
        """Persist a batch of parsed expenses for a user (always in UAH).

        Incoming transfers (top-ups, cashback, salary, etc.) are rejected here
        as a safety net even if the AI accidentally returns one.

        Expenses are logged at the receipt time (``fallback_dt``, i.e. now) so
        they always show up under "today". A purchase time parsed from the
        screenshot is only kept when it falls on the same calendar day, since
        OCR/AI often reports a past or wrongly-guessed date.
        """
        fallback_dt = fallback_dt or datetime.utcnow()
        created: list[Expense] = []
        for item in parsed:
            if looks_like_income(item.merchant):
                continue
            occurred_at = item.occurred_at
            if occurred_at is None or occurred_at.date() != fallback_dt.date():
                occurred_at = fallback_dt
            expense = Expense(
                user_id=user_id,
                amount=item.amount,
                currency=CURRENCY_CODE,
                occurred_at=occurred_at,
                merchant=item.merchant,
                raw_text=raw_text,
            )
            self.session.add(expense)
            created.append(expense)
        await self.session.flush()
        return created

    async def delete_all_for_user(self, user_id: int) -> int:
        """Delete every expense for a user. Returns the number removed."""
        result = await self.session.execute(
            delete(Expense).where(Expense.user_id == user_id)
        )
        return result.rowcount or 0

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
            .order_by(Expense.occurred_at.asc())
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
