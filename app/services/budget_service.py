"""Budget persistence operations."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import CURRENCY_CODE
from app.models import Budget, BudgetPeriod


class BudgetService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def set_budget(
        self,
        user_id: int,
        period: BudgetPeriod,
        amount: float,
        currency: str = CURRENCY_CODE,
    ) -> Budget:
        """Create or update the user's budget for the given period (UAH)."""
        result = await self.session.execute(
            select(Budget).where(
                Budget.user_id == user_id, Budget.period == period
            )
        )
        budget = result.scalar_one_or_none()
        if budget is None:
            budget = Budget(
                user_id=user_id,
                period=period,
                amount=amount,
                currency=CURRENCY_CODE,
            )
            self.session.add(budget)
        else:
            budget.amount = amount
            budget.currency = CURRENCY_CODE
        await self.session.flush()
        return budget

    async def delete_all_for_user(self, user_id: int) -> int:
        """Delete every budget for a user. Returns the number removed."""
        result = await self.session.execute(
            delete(Budget).where(Budget.user_id == user_id)
        )
        return result.rowcount or 0

    async def get_budget(
        self, user_id: int, period: BudgetPeriod
    ) -> Budget | None:
        result = await self.session.execute(
            select(Budget).where(
                Budget.user_id == user_id, Budget.period == period
            )
        )
        return result.scalar_one_or_none()

    async def all_budgets(self, user_id: int) -> list[Budget]:
        result = await self.session.execute(
            select(Budget).where(Budget.user_id == user_id)
        )
        return list(result.scalars().all())
