"""Start / help handlers."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.handlers.keyboards import main_menu_keyboard

router = Router(name="common")

WELCOME = (
    "👋 <b>Hi! I'm your expense tracker.</b>\n\n"
    "Just send me a <b>screenshot</b> of your banking app "
    "(Monobank, Privat24, A-Bank…) and I'll read the expenses and track your "
    "budget automatically. 📸\n\n"
    "<b>Quick start</b>\n"
    "• 📷 Send a screenshot to log expenses\n"
    "• 🎯 /set_week_budget 5000 — set a weekly budget\n"
    "• 🎯 /set_month_budget 20000 — set a monthly budget\n"
    "• 📅 /today — today's expenses\n"
    "• 📊 /stats — totals & remaining budget\n\n"
    "💱 All amounts are tracked in <b>UAH (₴)</b>.\n"
    "Type /help to see everything I can do."
)

HELP = (
    "🤖 <b>What I can do</b>\n\n"
    "<b>Logging</b>\n"
    "• 📷 Send a screenshot → I extract your expenses\n"
    "  (incoming transfers, top-ups & cashback are ignored)\n\n"
    "<b>Budgets</b>\n"
    "• /set_week_budget [amount]\n"
    "• /set_month_budget [amount]\n\n"
    "<b>Statistics</b>\n"
    "• /today — today's expenses\n"
    "• /stats — totals (today / week / month) & remaining budget\n\n"
    "<b>Manage</b>\n"
    "• 🗑 Reset Statistics (menu button) — delete all your data\n\n"
    "💡 Tip: clearer screenshots → better extraction."
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(WELCOME, reply_markup=main_menu_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP)
