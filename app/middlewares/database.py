"""Middleware that provides a DB session, services and the current user.

User setup commits before dispatch. Handlers own short database-only
transactions; closing the session rolls back any unfinished work.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.config import settings
from app.database.session import create_session_factory
from app.services import BudgetService, ExpenseService, UserService

logger = logging.getLogger(__name__)


class ServicesMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        message = event if isinstance(event, Message) else getattr(event, "message", None)
        if not isinstance(message, Message) or message.chat.type != "private":
            # Common commands need no DB and remain usable in groups.
            if isinstance(event, Message):
                command = (event.text or "").split(maxsplit=1)[0:1]
                name = command[0].split("@")[0] if command else ""
                if name in {"/start", "/help", "/cancel"}:
                    return await handler(event, data)
                await event.answer("Please use a private chat with me for expense tracking.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Please use a private chat with me.", show_alert=True)
            return None

        tg_user = data.get("event_from_user")
        if tg_user is None:
            return await handler(event, data)

        allowed = settings.allowed_user_id_set
        if allowed and tg_user.id not in allowed:
            logger.warning("Blocked unauthorized user %s", tg_user.id)
            if isinstance(event, Message):
                await event.answer("⛔ You are not authorized to use this bot.")
            return None

        factory = create_session_factory()
        async with factory() as session:
            async with session.begin():
                user_service = UserService(session)
                user = await user_service.get_or_create(
                    tg_user.id,
                    username=tg_user.username,
                    full_name=tg_user.full_name,
                )
            data["session"] = session
            data["user"] = user
            data["user_service"] = user_service
            data["expense_service"] = ExpenseService(session)
            data["budget_service"] = BudgetService(session)
            return await handler(event, data)
