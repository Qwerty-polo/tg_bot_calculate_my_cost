"""Statistics commands: /today and /stats (ultra-simple)."""

from __future__ import annotations

from datetime import datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.models import BudgetPeriod, User
from app.services import BudgetService, ExpenseService
from app.utils.formatting import format_stats, format_today
from app.utils.timeframe import day_range, month_range, week_range

router = Router(name="stats")


@router.message(Command("today"))
async def cmd_today(
    message: Message, user: User, expense_service: ExpenseService
) -> None:
    start, end = day_range(datetime.utcnow())
    expenses = await expense_service.list_in_range(user.id, start, end)
    await message.answer(format_today(expenses))


@router.message(Command("stats"))
async def cmd_stats(
    message: Message,
    user: User,
    expense_service: ExpenseService,
    budget_service: BudgetService,
) -> None:
    now = datetime.utcnow()
    day_start, day_end = day_range(now)
    week_start, week_end = week_range(now)
    month_start, month_end = month_range(now)

    today_total = await expense_service.total_in_range(user.id, day_start, day_end)
    week_total = await expense_service.total_in_range(user.id, week_start, week_end)
    month_total = await expense_service.total_in_range(user.id, month_start, month_end)

    week_budget = await budget_service.get_budget(user.id, BudgetPeriod.WEEK)
    month_budget = await budget_service.get_budget(user.id, BudgetPeriod.MONTH)

    await message.answer(
        format_stats(
            today_total=today_total,
            week_total=week_total,
            month_total=month_total,
            week_budget=float(week_budget.amount) if week_budget else None,
            month_budget=float(month_budget.amount) if month_budget else None,
        )
    )
