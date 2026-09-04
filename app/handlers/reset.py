"""Reset Statistics: wipe a single user's expenses, budgets and analytics."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.handlers.keyboards import (
    RESET_BUTTON,
    RESET_CANCEL,
    RESET_CONFIRM,
    reset_confirm_keyboard,
)
from app.models import User
from app.services import BudgetService, ExpenseService

logger = logging.getLogger(__name__)

router = Router(name="reset")


@router.message(F.text == RESET_BUTTON)
async def cmd_reset_prompt(message: Message) -> None:
    """Ask for confirmation before deleting anything."""
    await message.answer(
        "⚠️ <b>Are you sure?</b>\n\n"
        "This will permanently delete <b>ALL</b> your expenses and budgets. "
        "This cannot be undone.",
        reply_markup=reset_confirm_keyboard(),
    )


@router.callback_query(F.data == RESET_CANCEL)
async def on_reset_cancel(callback: CallbackQuery) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text("👍 Cancelled — nothing was deleted.")
    await callback.answer()


@router.callback_query(F.data == RESET_CONFIRM)
async def on_reset_confirm(
    callback: CallbackQuery,
    user: User,
    expense_service: ExpenseService,
    budget_service: BudgetService,
    state: FSMContext,
) -> None:
    """Delete everything that belongs to the requesting user only."""
    expenses_deleted = await expense_service.delete_all_for_user(user.id)
    budgets_deleted = await budget_service.delete_all_for_user(user.id)

    # Drop any in-progress conversation (e.g. a pending budget prompt).
    await state.clear()

    logger.info(
        "Reset stats for user %s: %s expenses, %s budgets",
        user.id,
        expenses_deleted,
        budgets_deleted,
    )

    summary = (
        "🗑 <b>Statistics reset complete.</b>\n\n"
        f"• Expenses deleted: <b>{expenses_deleted}</b>\n"
        f"• Budgets removed: <b>{budgets_deleted}</b>\n\n"
        "You're starting fresh — send a screenshot to log new expenses. 📸"
    )
    if isinstance(callback.message, Message):
        await callback.message.edit_text(summary)
    await callback.answer("Done")
