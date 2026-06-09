"""Bot and dispatcher factory functions."""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from app.config import settings
from app.handlers import get_root_router
from app.middlewares import LoggingMiddleware, ServicesMiddleware

BOT_COMMANDS = [
    BotCommand(command="start", description="Start / how it works"),
    BotCommand(command="help", description="Show help"),
    BotCommand(command="today", description="Today's expenses"),
    BotCommand(command="week", description="This week's expenses"),
    BotCommand(command="month", description="This month's expenses"),
    BotCommand(command="categories", description="Spending by category"),
    BotCommand(command="stats", description="Full AI financial analysis"),
    BotCommand(command="budget_status", description="Budget status"),
    BotCommand(command="set_week_budget", description="Set weekly budget"),
    BotCommand(command="set_month_budget", description="Set monthly budget"),
]


def create_bot() -> Bot:
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())

    # Middlewares: logging (outer) + services/session (per message & callback).
    dispatcher.message.outer_middleware(LoggingMiddleware())
    dispatcher.message.middleware(ServicesMiddleware())
    dispatcher.callback_query.middleware(ServicesMiddleware())

    dispatcher.include_router(get_root_router())
    return dispatcher


async def set_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(BOT_COMMANDS)
