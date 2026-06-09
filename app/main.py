"""Application entrypoint: boots the bot and starts long-polling."""

from __future__ import annotations

import asyncio
import logging

from app.bot import create_bot, create_dispatcher, set_bot_commands
from app.config import settings
from app.database.session import init_models
from app.utils.logging_config import setup_logging

logger = logging.getLogger(__name__)


async def main() -> None:
    setup_logging(settings.log_level)

    if not settings.bot_token:
        raise RuntimeError(
            "BOT_TOKEN is not set. Copy .env.example to .env and fill it in."
        )
    if not settings.has_openai:
        logger.warning(
            "OPENAI_API_KEY is not set — falling back to heuristic parsing and "
            "template-based insights."
        )

    # Create tables on first run (production should use Alembic migrations).
    await init_models()

    bot = create_bot()
    dispatcher = create_dispatcher()

    await set_bot_commands(bot)
    logger.info("Bot starting (long-polling)…")
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


def run() -> None:
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")


if __name__ == "__main__":
    run()
