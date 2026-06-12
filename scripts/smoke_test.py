"""Manual end-to-end smoke test of the non-Telegram pipeline.

Generates a synthetic banking-style screenshot, runs OCR -> parse -> DB ->
analytics -> charts. Run with: python -m scripts.smoke_test
"""

from __future__ import annotations

import asyncio
import io
import os
from datetime import datetime

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./data/smoke.db")

from PIL import Image, ImageDraw  # noqa: E402

from app.ai import generate_financial_insights, parse_transactions  # noqa: E402
from app.analytics import AnalyticsService  # noqa: E402
from app.charts import category_pie_chart, weekly_spending_chart  # noqa: E402
from app.database.session import init_models, session_scope  # noqa: E402
from app.models import BudgetPeriod  # noqa: E402
from app.ocr import extract_text  # noqa: E402
from app.services import BudgetService, ExpenseService, UserService  # noqa: E402
from app.utils.timeframe import week_range  # noqa: E402


def make_screenshot() -> bytes:
    img = Image.new("RGB", (700, 360), "white")
    draw = ImageDraw.Draw(img)
    lines = [
        "Recent transactions",
        "Rozetka          1 850.00 UAH",
        "Silpo              230.50 UAH",
        "Uklon              120.00 UAH",
        "Netflix            199.00 UAH",
        "McDonalds          340.00 UAH",
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
        print(f"  {p.amount} {p.currency} - {p.merchant} [{p.category.value}]")

    async with session_scope() as session:
        user = await UserService(session).get_or_create(
            12345, username="tester", full_name="Test User"
        )
        expenses = ExpenseService(session)
        budgets = BudgetService(session)
        await expenses.add_many(user.id, parsed, raw_text=text)
        await budgets.set_budget(user.id, BudgetPeriod.WEEK, 5000, user.currency)

        analytics = AnalyticsService(expenses, budgets)
        metrics = await analytics.build_metrics(user, BudgetPeriod.WEEK)
        print("\n=== METRICS ===")
        for key in (
            "total_spent",
            "budget",
            "budget_used_pct",
            "budget_remaining",
            "top_category",
            "biggest_expense",
            "daily_average",
        ):
            print(f"  {key}: {metrics.get(key)}")

        insight = await generate_financial_insights(metrics)
        print("\n=== INSIGHT (template fallback) ===")
        print(insight)

        pie = await category_pie_chart(metrics["categories"])
        week_start, week_end = week_range(datetime.utcnow())
        daily = await expenses.daily_totals(user.id, week_start, week_end)
        bar = await weekly_spending_chart(daily)
        print(f"\n=== CHARTS ===\n  pie bytes: {len(pie or b'')}, bar bytes: {len(bar or b'')}")


if __name__ == "__main__":
    asyncio.run(main())
