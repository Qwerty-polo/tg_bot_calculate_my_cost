"""Start / help handlers."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

router = Router(name="common")

WELCOME = (
    "👋 <b>Hi! I'm your AI expense tracker.</b>\n\n"
    "Just send me a <b>screenshot</b> of your banking app "
    "(Monobank, Privat24, A-Bank…) and I'll read the transactions, "
    "categorize them and track your budget automatically. 📸\n\n"
    "<b>Quick start</b>\n"
    "• 📷 Send a screenshot to log expenses\n"
    "• 🎯 /set_week_budget 5000 — set a weekly budget\n"
    "• 🎯 /set_month_budget 20000 — set a monthly budget\n"
    "• 📊 /stats — full financial analysis\n\n"
    "Type /help to see everything I can do."
)

HELP = (
    "🤖 <b>What I can do</b>\n\n"
    "<b>Logging</b>\n"
    "• 📷 Send a screenshot → I extract & categorize expenses\n\n"
    "<b>Budgets</b>\n"
    "• /set_week_budget [amount]\n"
    "• /set_month_budget [amount]\n"
    "• /budget_status\n\n"
    "<b>Statistics</b>\n"
    "• /today — today's expenses\n"
    "• /week — this week's expenses\n"
    "• /month — this month's expenses\n"
    "• /categories — spending by category (with chart)\n"
    "• /stats — full AI financial analysis + charts\n\n"
    "💡 Tip: clearer screenshots → better extraction."
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(WELCOME)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP)
