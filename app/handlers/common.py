"""Start / help handlers."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.handlers.keyboards import main_menu_keyboard

router = Router(name="common")

WELCOME = (
    "👋 <b>Hi! I'm your expense tracker.</b>\n\n"
    "Just send me a <b>screenshot</b> of your banking app "
    "(Monobank, Privat24, A-Bank…) and I'll read the expenses and track your "
    "budget after you confirm the results. 📸\n\n"
    "<b>Quick start</b>\n"
    "• 📷 Send a screenshot → review → confirm expenses\n"
    "• 🎯 /set_week_budget 5000 — set a weekly budget\n"
    "• 🎯 /set_month_budget 20000 — set a monthly budget\n"
    "• 📅 /today — today's expenses\n"
    "• 📊 /stats — totals & remaining budget\n\n"
    "💱 Only <b>UAH (₴)</b> is supported; other currencies are not converted.\n"
    "🕒 Default timezone: Europe/Kyiv. Change it with /timezone.\n"
    "Type /help to see everything I can do."
)

HELP = (
    "🤖 <b>What I can do</b>\n\n"
    "<b>Logging</b>\n"
    "• 📷 Send a screenshot → review dates and amounts → confirm\n"
    "  (incoming transfers, top-ups & cashback are ignored)\n\n"
    "<b>Budgets</b>\n"
    "• /set_week_budget [amount]\n"
    "• /set_month_budget [amount]\n\n"
    "• /cancel — cancel any pending action\n\n"
    "<b>Statistics</b>\n"
    "• /today — today's expenses\n"
    "• /stats — totals (today / week / month) & remaining budget\n\n"
    "<b>Manage</b>\n"
    "• /expenses [page] — history, including older purchases\n"
    "• /delete ID — remove one expense after confirmation\n"
    "• /timezone [Europe/Kyiv] — local dates and statistics\n"
    "• 🗑 Reset Statistics — delete expenses, budgets and upload history\n\n"
    "💡 Tip: clearer screenshots → better extraction."
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    if message.chat.type != "private":
        await message.answer(
            "Hi! Open a private chat with me to track expenses. Use /help for help."
        )
        return
    await message.answer(WELCOME, reply_markup=main_menu_keyboard())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Cancelled. You can send a screenshot or start a new command.")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP)
