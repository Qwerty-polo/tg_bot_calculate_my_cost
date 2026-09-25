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
from app.utils.money import validate_amount

router = Router(name="budgets")

# Either a space-grouped number (e.g. "1 850,50") or a plain run of digits.
_AMOUNT_RE = re.compile(
    r"-?\d{1,3}(?:[ \u00a0]\d{3})+(?:[.,]\d+)?|-?\d+(?:[.,]\d+)?"
)


def parse_amount(text: str | None) -> float | None:
    """Parse a positive monetary amount from free text."""
    if not text:
        return None
    matches = list(_AMOUNT_RE.finditer(text))
    if len(matches) != 1:
        return None
    match = matches[0]
    # Reject partial numeric tokens (1e3, 12:30, dates, malformed decimals).
    before, after = text[:match.start()], text[match.end():]
    if (before and not before[-1].isspace()) or (after and not after[0].isspace()):
        return None
    cleaned = match.group(0).replace("\u00a0", "").replace(" ", "").replace(",", ".")
    try:
        value = validate_amount(float(cleaned))
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
    state: FSMContext,
) -> None:
    async with budget_service.session.begin():
        budget = await budget_service.set_budget(user.id, period, amount, user.currency)
    await state.clear()
    label = "weekly" if period is BudgetPeriod.WEEK else "monthly"
    await message.answer(
        f"🎯 Your <b>{label}</b> budget is set to "
        f"<b>{fmt_money(float(budget.amount))}</b>.\n"
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
    await state.clear()
    amount = parse_amount(command.args)
    if amount is None:
        await state.set_state(BudgetStates.waiting_for_week)
        await message.answer("💬 How much is your <b>weekly</b> budget? (e.g. 5000)")
        return
    await _apply_budget(message, user, budget_service, BudgetPeriod.WEEK, amount, state)


@router.message(Command("set_month_budget"))
async def cmd_set_month_budget(
    message: Message,
    command: CommandObject,
    user: User,
    budget_service: BudgetService,
    state: FSMContext,
) -> None:
    await state.clear()
    amount = parse_amount(command.args)
    if amount is None:
        await state.set_state(BudgetStates.waiting_for_month)
        await message.answer("💬 How much is your <b>monthly</b> budget? (e.g. 20000)")
        return
    await _apply_budget(message, user, budget_service, BudgetPeriod.MONTH, amount, state)


@router.message(BudgetStates.waiting_for_week, F.text, ~F.text.startswith("/"))
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
    await _apply_budget(message, user, budget_service, BudgetPeriod.WEEK, amount, state)


@router.message(BudgetStates.waiting_for_month, F.text, ~F.text.startswith("/"))
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
    await _apply_budget(message, user, budget_service, BudgetPeriod.MONTH, amount, state)
