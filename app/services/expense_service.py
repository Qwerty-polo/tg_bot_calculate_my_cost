"""Expense persistence and aggregation queries."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import looks_like_income
from app.ai.schemas import ParsedExpense
from app.config import CURRENCY_CODE
from app.models import Expense, Upload
from app.utils.money import validate_amount, validate_currency
from app.utils.timeframe import DEFAULT_TIMEZONE, as_utc


class ExpenseService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_upload(
        self, user_id: int, digest: str, parsed: list[ParsedExpense], *, raw_text: str,
        fallback_dt: datetime | None = None, timezone: str = DEFAULT_TIMEZONE,
    ) -> list[Expense] | None:
        """Return None for a duplicate. Caller commits marker and rows together."""
        parsed = [item for item in parsed if not looks_like_income(item.merchant)]
        if not parsed:
            return []
        result = await self.session.execute(
            insert(Upload).values(user_id=user_id, digest=digest).on_conflict_do_nothing(
                index_elements=["user_id", "digest"]
            )
        )
        if result.rowcount == 0:
            return None
        return await self.add_many(
            user_id, parsed, raw_text=raw_text, fallback_dt=fallback_dt, timezone=timezone
        )

    async def add_many(
        self,
        user_id: int,
        parsed: list[ParsedExpense],
        *,
        raw_text: str | None = None,
        fallback_dt: datetime | None = None,
        timezone: str = DEFAULT_TIMEZONE,
    ) -> list[Expense]:
        """Persist a batch of parsed expenses for a user (always in UAH).

        Incoming transfers (top-ups, cashback, salary, etc.) are rejected here
        as a safety net even if the AI accidentally returns one.

        Parsed local purchase dates are normalized to UTC. Only missing dates
        use the upload receipt time; created_at records the persistence time.
        """
        fallback_dt = as_utc(fallback_dt or datetime.now(UTC))
        created: list[Expense] = []
        for item in parsed:
            if looks_like_income(item.merchant):
                continue
            validate_currency(item.currency)
            occurred_at = (
                as_utc(item.occurred_at, timezone) if item.occurred_at else fallback_dt
            )
            expense = Expense(
                user_id=user_id,
                amount=validate_amount(item.amount),
                currency=CURRENCY_CODE,
                occurred_at=occurred_at,
                merchant=item.merchant,
                raw_text=raw_text,
            )
            self.session.add(expense)
            created.append(expense)
        await self.session.flush()
        return created

    async def has_upload(self, user_id: int, digest: str) -> bool:
        return await self.session.get(Upload, (user_id, digest)) is not None

    async def get_for_user(self, user_id: int, expense_id: int) -> Expense | None:
        return await self.session.scalar(
            select(Expense).where(Expense.user_id == user_id, Expense.id == expense_id)
        )

    async def delete_for_user(self, user_id: int, expense_id: int) -> bool:
        result = await self.session.execute(
            delete(Expense).where(Expense.user_id == user_id, Expense.id == expense_id)
        )
        return bool(result.rowcount)

    async def recent(self, user_id: int, page: int, page_size: int = 10) -> list[Expense]:
        result = await self.session.scalars(
            select(Expense).where(Expense.user_id == user_id)
            .order_by(Expense.occurred_at.desc(), Expense.id.desc())
            .offset((page - 1) * page_size).limit(page_size)
        )
        return list(result)

    async def delete_all_for_user(self, user_id: int) -> int:
        """Delete every expense for a user. Returns the number removed."""
        await self.session.execute(delete(Upload).where(Upload.user_id == user_id))
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
