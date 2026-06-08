"""Budget commands: /set_week_budget and /set_month_budget."""

from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from app.models import BudgetPeriod, User
from app.services import BudgetService
from app.utils.formatting import fmt_money

router = Router(name="budgets")

# Either a space-grouped number (e.g. "1 850,50") or a plain run of digits.
_AMOUNT_RE = re.compile(
    r"-?\d{1,3}(?:[ \u00a0]\d{3})+(?:[.,]\d+)?|-?\d+(?:[.,]\d+)?"
)


def parse_amount(text: str | None) -> float | None:
    """Parse a positive monetary amount from free text."""
    if not text:
        return None
    match = _AMOUNT_RE.search(text)
    if not match:
        return None
    cleaned = match.group(0).replace("\u00a0", "").replace(" ", "").replace(",", ".")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if value > 0 else None


class BudgetStates(StatesGroup):
    waiting_for_week = State()
    waiting_for_month = State()


async def _apply_budget(
    message: Message,
    user: User,
    budget_service: BudgetService,
    period: BudgetPeriod,
    amount: float,
) -> None:
    budget = await budget_service.set_budget(
        user.id, period, amount, user.currency
    )
    label = "weekly" if period is BudgetPeriod.WEEK else "monthly"
    await message.answer(
        f"🎯 Your <b>{label}</b> budget is set to "
        f"<b>{fmt_money(float(budget.amount), budget.currency)}</b>.\n"
        f"I'll track your spending against it automatically."
    )


@router.message(Command("set_week_budget"))
async def cmd_set_week_budget(
    message: Message,
    command: CommandObject,
    user: User,
    budget_service: BudgetService,
    state: FSMContext,
) -> None:
    amount = parse_amount(command.args)
    if amount is None:
        await state.set_state(BudgetStates.waiting_for_week)
        await message.answer("💬 How much is your <b>weekly</b> budget? (e.g. 5000)")
        return
    await _apply_budget(message, user, budget_service, BudgetPeriod.WEEK, amount)


@router.message(Command("set_month_budget"))
async def cmd_set_month_budget(
    message: Message,
    command: CommandObject,
    user: User,
    budget_service: BudgetService,
    state: FSMContext,
) -> None:
    amount = parse_amount(command.args)
    if amount is None:
        await state.set_state(BudgetStates.waiting_for_month)
        await message.answer("💬 How much is your <b>monthly</b> budget? (e.g. 20000)")
        return
    await _apply_budget(message, user, budget_service, BudgetPeriod.MONTH, amount)


@router.message(BudgetStates.waiting_for_week, F.text)
async def receive_week_budget(
    message: Message,
    user: User,
    budget_service: BudgetService,
    state: FSMContext,
) -> None:
    amount = parse_amount(message.text)
    if amount is None:
        await message.answer("⚠️ Please send a positive number, e.g. 5000.")
        return
    await state.clear()
    await _apply_budget(message, user, budget_service, BudgetPeriod.WEEK, amount)


@router.message(BudgetStates.waiting_for_month, F.text)
async def receive_month_budget(
    message: Message,
    user: User,
    budget_service: BudgetService,
    state: FSMContext,
) -> None:
    amount = parse_amount(message.text)
    if amount is None:
        await message.answer("⚠️ Please send a positive number, e.g. 20000.")
        return
    await state.clear()
    await _apply_budget(message, user, budget_service, BudgetPeriod.MONTH, amount)
