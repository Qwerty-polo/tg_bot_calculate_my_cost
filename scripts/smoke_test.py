"""Manual end-to-end smoke test of the non-Telegram pipeline.

Generates a synthetic banking-style screenshot, runs OCR -> parse -> DB ->
simple stats. Run with: python -m scripts.smoke_test
"""

from __future__ import annotations

import asyncio
import io
import os
from datetime import datetime

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./data/smoke.db")

from PIL import Image, ImageDraw  # noqa: E402

from app.ai import parse_transactions  # noqa: E402
from app.database.session import init_models, session_scope  # noqa: E402
from app.models import BudgetPeriod  # noqa: E402
from app.ocr import extract_text  # noqa: E402
from app.services import BudgetService, ExpenseService, UserService  # noqa: E402
from app.utils.formatting import format_stats, format_today  # noqa: E402
from app.utils.timeframe import day_range, month_range, week_range  # noqa: E402


def make_screenshot() -> bytes:
    img = Image.new("RGB", (700, 410), "white")
    draw = ImageDraw.Draw(img)
    lines = [
        "Recent transactions",
        "Rozetka          1 850.00 UAH",
        "Silpo              230.50 UAH",
        "Uklon              120.00 UAH",
        "Netflix            199.00 UAH",
        "McDonalds          340.00 UAH",
        "Cashback           5 000.00 UAH",  # incoming — must be skipped
    ]
    y = 20
    for line in lines:
        draw.text((20, y), line, fill="black")
        y += 50
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def main() -> None:
    await init_models()
    image = make_screenshot()

    text = await extract_text(image)
    print("=== OCR TEXT ===")
    print(text)

    parsed = await parse_transactions(text)
    print(f"\n=== PARSED {len(parsed)} EXPENSES ===")
    for p in parsed:
        print(f"  {p.amount} {p.currency} - {p.merchant}")

    async with session_scope() as session:
        user = await UserService(session).get_or_create(
            12345, username="tester", full_name="Test User"
        )
        expenses = ExpenseService(session)
        budgets = BudgetService(session)
        created = await expenses.add_many(user.id, parsed, raw_text=text)
        await budgets.set_budget(user.id, BudgetPeriod.WEEK, 5000, user.currency)
        await budgets.set_budget(user.id, BudgetPeriod.MONTH, 15000, user.currency)

        now = datetime.utcnow()
        today = await expenses.list_in_range(user.id, *day_range(now))
        print("\n=== TODAY ===")
        print(format_today(today))

        stats = format_stats(
            today_total=await expenses.total_in_range(user.id, *day_range(now)),
            week_total=await expenses.total_in_range(user.id, *week_range(now)),
            month_total=await expenses.total_in_range(user.id, *month_range(now)),
            week_budget=5000,
            month_budget=15000,
        )
        print("\n=== STATS ===")
        print(stats)
        print(f"\nStored {len(created)} expense(s) (incoming transfers skipped).")


if __name__ == "__main__":
    asyncio.run(main())
