"""Expense history, individual deletion and calendar timezone preferences."""

from html import escape
from secrets import token_hex
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers.keyboards import action_keyboard
from app.models import User
from app.services import ExpenseService
from app.utils.formatting import format_expense_line
from app.utils.messages import send_pages

router = Router(name="expenses")


class DeleteStates(StatesGroup):
    confirmation = State()


def positive_id(value: str | None) -> int | None:
    if not value or not value.isascii() or not value.isdecimal() or len(value) > 18:
        return None
    number = int(value)
    return number if number > 0 else None


@router.message(Command("expenses"))
async def cmd_expenses(
    message: Message, command: CommandObject, user: User, expense_service: ExpenseService
) -> None:
    page = positive_id(command.args or "1")
    if page is None or page > 1_000_000:
        await message.answer("Use /expenses or /expenses 2 to view a page of your history.")
        return
    async with expense_service.session.begin():
        items = await expense_service.recent(user.id, page)
    if not items:
        await message.answer("No expenses on this page. Use /expenses to return to the first page.")
        return
    lines = [f"<b>Expense history · page {page}</b>", f"Timezone: {escape(user.timezone)}", ""]
    lines.extend(format_expense_line(item, user.timezone) for item in items)
    lines.extend(["", "Delete an expense with /delete ID."])
    if len(items) == 10:
        lines.append(f"Next page: /expenses {page + 1}")
    await send_pages(message, "\n".join(lines))


@router.message(Command("delete"))
async def cmd_delete(
    message: Message, command: CommandObject, user: User,
    expense_service: ExpenseService, state: FSMContext,
) -> None:
    if await state.get_state() is not None:
        await message.answer(
            "Finish your pending action, or use /cancel before deleting an expense."
        )
        return
    expense_id = positive_id(command.args)
    if expense_id is None:
        await message.answer("Use /delete ID. Find expense IDs with /expenses or /today.")
        return
    async with expense_service.session.begin():
        expense = await expense_service.get_for_user(user.id, expense_id)
    if expense is None:
        await message.answer("Expense not found in your history.")
        return
    token = token_hex(8)
    await state.set_state(DeleteStates.confirmation)
    await state.set_data({"token": token, "expense_id": expense_id})
    await message.answer(
        "<b>Delete this expense?</b>\n\n" + format_expense_line(expense, user.timezone)
        + "\n\nYour budgets and other expenses will remain.",
        reply_markup=action_keyboard("delete", token, "Delete expense"),
    )


@router.callback_query(F.data.startswith("delete:"))
async def on_delete_action(
    callback: CallbackQuery, user: User, expense_service: ExpenseService, state: FSMContext
) -> None:
    parts = (callback.data or "").split(":")
    pending = await state.get_data()
    if (
        len(parts) != 3 or parts[1] not in {"confirm", "cancel"}
        or await state.get_state() != DeleteStates.confirmation.state
        or pending.get("token") != parts[2]
    ):
        await callback.answer("This deletion request is no longer active.")
        return
    if parts[1] == "cancel":
        text = "Cancelled. Nothing was deleted."
    else:
        async with expense_service.session.begin():
            deleted = await expense_service.delete_for_user(user.id, pending["expense_id"])
        text = "Expense deleted. Statistics updated." if deleted else "Expense already removed."
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text)
    await callback.answer()


@router.message(Command("timezone"))
async def cmd_timezone(
    message: Message, command: CommandObject, user: User, session: AsyncSession
) -> None:
    timezone = (command.args or "").strip()
    if not timezone:
        await message.answer(
            f"Your timezone: <b>{escape(user.timezone)}</b>.\n"
            "Change it with /timezone Europe/Kyiv or /timezone Europe/Warsaw."
        )
        return
    try:
        if len(timezone) > 64:
            raise ValueError("Timezone name too long")
        ZoneInfo(timezone)
    except (ValueError, ZoneInfoNotFoundError):
        await message.answer("Unknown timezone. Example: /timezone Europe/Kyiv")
        return
    async with session.begin():
        user.timezone = timezone
    await message.answer(
        f"Timezone set to <b>{escape(timezone)}</b>. Statistics now use your local calendar.\n"
        "An open screenshot preview keeps the timezone displayed on that preview."
    )
