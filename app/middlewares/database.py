"""Middleware that provides a DB session, services and the current user.

Wrapping the handler in a single transactional session keeps handlers simple:
they receive ready-to-use services and a persisted ``User`` row, and the
session is committed (or rolled back) automatically.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

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
            try:
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
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise
