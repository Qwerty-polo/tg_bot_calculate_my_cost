"""Bot and dispatcher factory functions."""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation
from aiogram.types import BotCommand

from app.config import settings
from app.handlers import get_root_router
from app.middlewares import LoggingMiddleware, ServicesMiddleware

BOT_COMMANDS = [
    BotCommand(command="start", description="Start / how it works"),
    BotCommand(command="help", description="Show help"),
    BotCommand(command="cancel", description="Cancel a pending action"),
    BotCommand(command="today", description="Today's expenses"),
    BotCommand(command="stats", description="Totals & remaining budget"),
    BotCommand(command="expenses", description="Expense history and IDs"),
    BotCommand(command="delete", description="Delete an expense by ID"),
    BotCommand(command="timezone", description="View or change your timezone"),
    BotCommand(command="set_week_budget", description="Set weekly budget"),
    BotCommand(command="set_month_budget", description="Set monthly budget"),
]


def create_bot() -> Bot:
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage(), events_isolation=SimpleEventIsolation())

    # Middlewares: logging (outer) + services/session (per message & callback).
    dispatcher.message.outer_middleware(LoggingMiddleware())
    dispatcher.message.middleware(ServicesMiddleware())
    dispatcher.callback_query.middleware(ServicesMiddleware())

    dispatcher.include_router(get_root_router())
    return dispatcher


async def set_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(BOT_COMMANDS)
