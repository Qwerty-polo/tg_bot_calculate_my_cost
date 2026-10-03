"""Render actual bot responses from a deterministic, entirely offline demo."""

from __future__ import annotations

import asyncio
import copy
import io
import json
import re
import textwrap
from datetime import UTC, datetime
from html import escape, unescape
from pathlib import Path
from unittest.mock import AsyncMock, patch

from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendMessage
from aiogram.types import CallbackQuery, Chat, Message, PhotoSize, Update, User
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.ai.schemas import ParsedExpenseList
from app.database.base import Base
from app.handlers import budgets, common, expenses, reset, screenshots, stats
from app.middlewares.database import ServicesMiddleware
from app.models import Expense

ROOT = Path(__file__).resolve().parents[1]
DEMO_NOW = datetime(2026, 10, 3, 12, tzinfo=UTC)


class DemoClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return DEMO_NOW.astimezone(tz) if tz else DEMO_NOW.replace(tzinfo=None)


class DemoTransport(BaseSession):
    def __init__(self):
        super().__init__()
        self.messages = []

    async def close(self):
        pass

    async def make_request(self, bot, method, timeout=None):
        if isinstance(method, AnswerCallbackQuery):
            return True
        if not isinstance(method, SendMessage | EditMessageText):
            raise RuntimeError("Unexpected Telegram method in offline demo")
        self.messages.append(method)
        return Message(
            message_id=len(self.messages), date=DEMO_NOW, text=method.text,
            chat=Chat(id=method.chat_id, type="private"), reply_markup=method.reply_markup,
        ).as_(bot)

    async def stream_content(self, *args, **kwargs):
        raise RuntimeError("The offline demo must not use the network")
        yield b""


async def demo_responses() -> list[tuple[str, str]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    transport = DemoTransport()
    bot = Bot("123456:OFFLINE_DEMO", session=transport)
    dispatcher = Dispatcher(storage=MemoryStorage(), events_isolation=SimpleEventIsolation())
    dispatcher.message.middleware(ServicesMiddleware())
    dispatcher.callback_query.middleware(ServicesMiddleware())
    for module in (common, reset, expenses, budgets, stats, screenshots):
        dispatcher.include_router(copy.deepcopy(module.router))
    actor = User(id=1001, is_bot=False, first_name="Demo")
    state = dispatcher.fsm.get_context(bot=bot, chat_id=actor.id, user_id=actor.id)
    fixture = (ROOT / "docs/demo/transactions.json").read_text(encoding="utf-8")
    parsed = ParsedExpenseList.model_validate_json(fixture).expenses

    async def send(text=None, *, photo=False, callback=None):
        message = Message(
            message_id=1, date=DEMO_NOW, chat=Chat(id=actor.id, type="private"),
            from_user=actor, text=text,
            photo=[PhotoSize(file_id="demo", file_unique_id="demo", width=900, height=600)]
            if photo else None,
        )
        update = Update(update_id=1, callback_query=CallbackQuery(
            id="demo", from_user=actor, chat_instance="demo", message=message, data=callback,
        )) if callback else Update(update_id=1, message=message)
        await dispatcher.feed_update(bot, update)

    async def count_expenses():
        async with factory() as session:
            return await session.scalar(select(func.count()).select_from(Expense))

    try:
        with (
            patch("app.middlewares.database.create_session_factory", return_value=factory),
            patch("app.middlewares.database.settings") as demo_settings,
            patch.object(bot, "download", AsyncMock(return_value=io.BytesIO(b"demo image"))),
            patch.object(screenshots, "extract_text", AsyncMock(return_value="Fictional demo OCR")),
            patch.object(screenshots, "parse_transactions", AsyncMock(return_value=parsed)),
            patch.object(stats, "datetime", DemoClock),
        ):
            demo_settings.allowed_user_id_set = set()
            await send("/set_week_budget 1000")
            await send("/set_month_budget 5000")
            await send(photo=True)
            review = transport.messages[-1].text
            assert await count_expenses() == 0
            token = (await state.get_data())["token"]
            await send(callback=f"upload:confirm:{token}")
            saved = transport.messages[-1].text
            assert await count_expenses() == 3
            await send("/stats")
            before_delete = transport.messages[-1].text
            assert "Total today: ₴350.50" in before_delete
            assert "Total this week: ₴425.50" in before_delete
            await send("/delete 2")
            deletion = transport.messages[-1].text
            token = (await state.get_data())["token"]
            await send(callback=f"delete:confirm:{token}")
            assert await count_expenses() == 2
            await send("/stats")
            after_delete = transport.messages[-1].text
            assert "Total today: ₴230.50" in after_delete
            return [
                ("01 / Review · nothing saved", review),
                ("02 / Confirm · dates preserved", saved),
                ("03 / Statistics · local calendar", before_delete),
                ("04 / Delete · one expense", deletion),
                ("05 / Updated statistics", after_delete),
            ]
    finally:
        await dispatcher.storage.close()
        await dispatcher.fsm.events_isolation.close()
        await bot.session.close()
        await engine.dispose()


def render_svg(responses: list[tuple[str, str]]) -> str:
    selected = [responses[0], responses[2], responses[4]]
    elements = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1320" height="900" '
        'viewBox="0 0 1320 900" role="img" aria-labelledby="title desc">',
        '<title id="title">Expense Tracker: review, confirm, manage</title>',
        '<desc id="desc">Offline demonstration with fictional transactions. '
        'Bot responses come from the real handlers and an in-memory database.</desc>',
        '<rect width="1320" height="900" rx="24" fill="#0b1421"/>',
        '<g font-family="Segoe UI,Arial,sans-serif">',
        '<text x="42" y="60" fill="#63e6c6" font-size="16" letter-spacing="3">'
        'TELEGRAM EXPENSE TRACKER</text>',
        '<text x="42" y="115" fill="#f0f6fc" font-size="38" font-weight="700">'
        'Review first. Keep your ledger accurate.</text>',
        '<text x="42" y="153" fill="#99acc2" font-size="17">'
        'Historical dates · UAH validation · Local budgets · Individual deletion</text>',
    ]
    for index, (title, body) in enumerate(selected):
        position = 42 + index * 418
        elements.extend([
            f'<rect x="{position}" y="194" width="400" height="590" rx="16" '
            'fill="#152337" stroke="#2c415b"/>',
            f'<text x="{position + 22}" y="232" fill="#63e6c6" font-size="16" '
            f'font-weight="600">{escape(title)}</text>',
        ])
        plain = unescape(re.sub(r"</?b>", "", body))
        lines = []
        for line in plain.splitlines():
            lines.extend(textwrap.wrap(line, width=39) or [""])
        for line_index, line in enumerate(lines):
            elements.append(
                f'<text x="{position + 22}" y="{272 + line_index * 22}" '
                f'fill="#e1eaf5" font-size="15">{escape(line)}</text>'
            )
        if index == 0:
            elements.extend([
                f'<rect x="{position + 22}" y="724" width="230" height="38" '
                'rx="9" fill="#247863"/>',
                f'<text x="{position + 42}" y="749" fill="white" font-size="15">'
                'Confirm expenses</text>',
            ])
    elements.extend([
        '<text x="42" y="833" fill="#99acc2" font-size="16">'
        'Fictional data · Offline rendering of actual bot responses · Simulated OCR/AI and Telegram'
        '</text>',
        '<text x="42" y="864" fill="#99acc2" font-size="15">'
        'The September 30 purchase stays in September. Deleting the taxi updates totals, '
        'not your budget.</text>',
        '</g></svg>',
    ])
    return "\n".join(elements)


def render_html(responses: list[tuple[str, str]]) -> str:
    cards = "".join(
        f'<article><h2>{escape(title)}</h2><div class="message">{body}</div></article>'
        for title, body in responses
    )
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Expense Tracker · Offline Demo</title>
<style>
body{margin:0;background:#0b1421;color:#e1eaf5;font:16px/1.6 system-ui,sans-serif}
main{max-width:1150px;margin:auto;padding:48px 24px}h1{font-size:40px;line-height:1.15}
h2{font-size:18px;color:#63e6c6}.note{color:#99acc2;max-width:850px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:22px}
article{padding:24px;background:#152337;border:1px solid #2c415b;border-radius:16px}
.message{white-space:pre-wrap;overflow-wrap:anywhere}code{color:#63e6c6}
</style></head><body><main><h1>Review first. Keep your ledger accurate.</h1>
<p class="note">Fictional transactions, actual bot responses. This offline walkthrough uses
the real handlers and an in-memory SQLite database. Telegram transport and OCR/AI are simulated;
this is not a live Telegram screenshot or an OCR accuracy benchmark.</p>
<p class="note">Demo date: October 3, 2026 · Europe/Kyiv. The September purchase keeps its date.
The taxi is removed individually after confirmation.</p><section class="grid">""" + cards + """
</section><p class="note">Rebuild with <code>python -m scripts.demo</code>.
No credentials, external calls or persistent database required.</p></main></body></html>
"""


async def main() -> None:
    responses = await demo_responses()
    output = ROOT / "docs/demo"
    output.mkdir(parents=True, exist_ok=True)
    (ROOT / "docs/images").mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_text(render_html(responses), encoding="utf-8")
    (output / "transcript.json").write_text(
        json.dumps(responses, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (ROOT / "docs/images/demo.svg").write_text(render_svg(responses), encoding="utf-8")
    print("Offline demo verified. Created docs/demo/index.html and docs/images/demo.svg")


if __name__ == "__main__":
    asyncio.run(main())
