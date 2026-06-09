"""Logging middleware for incoming updates."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

logger = logging.getLogger("bot.updates")


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            user = event.from_user
            content = event.text or ("<photo>" if event.photo else "<non-text>")
            logger.info(
                "msg from %s (%s): %s",
                user.id if user else "?",
                user.username if user else "?",
                content,
            )
        return await handler(event, data)
