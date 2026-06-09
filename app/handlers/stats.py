"""Statistics & analysis commands."""

from __future__ import annotations

from datetime import datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message

from app.ai import generate_financial_insights, generate_saving_recommendations
from app.analytics import AnalyticsService
from app.charts import (
    category_pie_chart,
    monthly_trend_chart,
    weekly_spending_chart,
)
from app.models import BudgetPeriod, User
from app.services import BudgetService, ExpenseService
from app.utils.formatting import (
    fmt_money,
    format_budget_status,
    format_categories,
    format_expense_list,
    format_period_header,
)
from app.utils.timeframe import day_range, month_range, week_range

router = Router(name="stats")


@router.message(Command("today"))
async def cmd_today(
    message: Message, user: User, expense_service: ExpenseService
) -> None:
    start, end = day_range(datetime.utcnow())
    expenses = await expense_service.list_in_range(user.id, start, end)
    await message.answer(format_expense_list(expenses, title="📅 Today's expenses"))


@router.message(Command("week"))
async def cmd_week(
    message: Message, user: User, expense_service: ExpenseService
) -> None:
    start, end = week_range(datetime.utcnow())
    expenses = await expense_service.list_in_range(user.id, start, end)
    await message.answer(format_expense_list(expenses, title="🗓️ This week's expenses"))


@router.message(Command("month"))
async def cmd_month(
    message: Message, user: User, expense_service: ExpenseService
) -> None:
    start, end = month_range(datetime.utcnow())
    expenses = await expense_service.list_in_range(user.id, start, end)
    await message.answer(format_expense_list(expenses, title="📆 This month's expenses"))


@router.message(Command("categories"))
async def cmd_categories(
    message: Message,
    user: User,
    expense_service: ExpenseService,
    budget_service: BudgetService,
) -> None:
    analytics = AnalyticsService(expense_service, budget_service)
    metrics = await analytics.build_metrics(user, BudgetPeriod.MONTH)
    await message.answer(format_categories(metrics))
    chart = await category_pie_chart(metrics.get("categories") or [])
    if chart:
        await message.answer_photo(
            BufferedInputFile(chart, filename="categories.png")
        )


@router.message(Command("budget_status"))
async def cmd_budget_status(
    message: Message,
    user: User,
    expense_service: ExpenseService,
    budget_service: BudgetService,
) -> None:
    analytics = AnalyticsService(expense_service, budget_service)
    for period in (BudgetPeriod.WEEK, BudgetPeriod.MONTH):
        metrics = await analytics.build_metrics(user, period)
        await message.answer(format_budget_status(metrics))


@router.message(Command("stats"))
async def cmd_stats(
    message: Message,
    user: User,
    expense_service: ExpenseService,
    budget_service: BudgetService,
) -> None:
    analytics = AnalyticsService(expense_service, budget_service)
    metrics = await analytics.build_metrics(user, BudgetPeriod.WEEK)

    await message.answer(format_period_header(metrics))

    # AI (or template) financial analysis.
    thinking = await message.answer("🧠 Analyzing your spending…")
    insight = await generate_financial_insights(metrics)
    await thinking.edit_text(f"🧠 <b>AI analysis</b>\n\n{insight}")

    # Budget status + categories.
    await message.answer(format_budget_status(metrics))
    await message.answer(format_categories(metrics))

    # Saving recommendations.
    recommendations = await generate_saving_recommendations(metrics)
    if recommendations:
        await message.answer(recommendations)

    # Unusual spending warning.
    unusual = metrics.get("unusual_expenses") or []
    if unusual:
        top = unusual[0]
        await message.answer(
            "🚨 <b>Unusually high spending detected</b>\n"
            f"{top.get('merchant') or 'A purchase'} — "
            f"{fmt_money(top['amount'], top['currency'])}"
        )

    # Charts.
    pie = await category_pie_chart(metrics.get("categories") or [])
    if pie:
        await message.answer_photo(BufferedInputFile(pie, filename="categories.png"))

    week_start, week_end = week_range(datetime.utcnow())
    daily = await expense_service.daily_totals(user.id, week_start, week_end)
    bar = await weekly_spending_chart(daily)
    if bar:
        await message.answer_photo(BufferedInputFile(bar, filename="weekly.png"))

    month_start, month_end = month_range(datetime.utcnow())
    monthly_daily = await expense_service.daily_totals(user.id, month_start, month_end)
    trend = await monthly_trend_chart(monthly_daily)
    if trend:
        await message.answer_photo(BufferedInputFile(trend, filename="monthly.png"))
