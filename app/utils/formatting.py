"""Human-friendly message formatting (HTML parse mode)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from html import escape

from app.ai.schemas import ParsedExpense
from app.config import CURRENCY_SYMBOL
from app.models import Expense
from app.utils.timeframe import DEFAULT_TIMEZONE, as_utc, local_datetime


def fmt_money(amount: float) -> str:
    """Format an amount in UAH as ``₴1 234`` (the bot is UAH-only).

    Whole amounts drop the decimals; fractional amounts keep two.
    """
    amount = float(amount)
    if amount == int(amount):
        body = f"{int(amount):,}".replace(",", " ")
    else:
        body = f"{amount:,.2f}".replace(",", " ")
    return f"{CURRENCY_SYMBOL}{body}"


def format_expense_line(expense: Expense, timezone: str = DEFAULT_TIMEZONE) -> str:
    merchant = escape((expense.merchant or "Purchase")[:120].replace("\n", " "))
    when = local_datetime(expense.occurred_at, timezone).strftime("%Y-%m-%d %H:%M")
    prefix = f"#{expense.id} · " if expense.id is not None else ""
    return f"{prefix}{when} — {merchant} {fmt_money(float(expense.amount))}"


def format_today(expenses: Sequence[Expense], timezone: str = DEFAULT_TIMEZONE) -> str:
    if not expenses:
        return "Today's expenses:\n\nNothing logged yet. Send a screenshot. 📸"
    lines = ["<b>Today's expenses:</b>", ""]
    total = 0.0
    for expense in expenses:
        lines.append(format_expense_line(expense, timezone))
        total += float(expense.amount)
    lines.append("")
    lines.append(f"<b>Total today:</b> {fmt_money(total)}")
    return "\n".join(lines)


def format_added_summary(expenses: Sequence[Expense], timezone: str = DEFAULT_TIMEZONE) -> str:
    if not expenses:
        return (
            "🤔 I couldn't find any expenses in that screenshot.\n"
            "Try a clearer image of the transactions list."
        )
    total = sum(float(e.amount) for e in expenses)
    lines = [f"✅ Added <b>{len(expenses)}</b> expense(s):", ""]
    lines.extend(format_expense_line(expense, timezone) for expense in expenses)
    lines.append("")
    lines.append(f"<b>Total:</b> {fmt_money(total)}")
    lines.append("Remove a mistake with /delete ID. View history with /expenses.")
    return "\n".join(lines)


def format_preview(
    parsed: Sequence[ParsedExpense], received_at: datetime, timezone: str
) -> str:
    lines = ["<b>Review expenses before saving</b>", f"Timezone: {escape(timezone)}", ""]
    for item in parsed:
        occurred_at = (
            as_utc(item.occurred_at, timezone) if item.occurred_at else as_utc(received_at)
        )
        expense = Expense(amount=item.amount, merchant=item.merchant, occurred_at=occurred_at)
        suffix = " (date missing; upload time)" if item.occurred_at is None else ""
        lines.append(format_expense_line(expense, timezone) + suffix)
    lines.extend([
        "", f"<b>Total:</b> {fmt_money(sum(item.amount for item in parsed))}",
        "Check amounts, merchants and dates. Nothing is saved yet.",
        "Confirm to save, or cancel and send a corrected screenshot.",
    ])
    return "\n".join(lines)


def format_stats(
    *,
    today_total: float,
    week_total: float,
    month_total: float,
    week_budget: float | None,
    month_budget: float | None,
) -> str:
    """Ultra-simple statistics block."""
    lines = ["<b>📊 Statistics</b>", ""]
    lines.append(f"Total today: {fmt_money(today_total)}")

    if week_budget is not None:
        lines.append(
            f"Total this week: {fmt_money(week_total)} / {fmt_money(week_budget)} limit"
        )
    else:
        lines.append(f"Total this week: {fmt_money(week_total)}")

    if month_budget is not None:
        lines.append(
            f"Total this month: {fmt_money(month_total)} / "
            f"{fmt_money(month_budget)} limit"
        )
    else:
        lines.append(f"Total this month: {fmt_money(month_total)}")

    if week_budget is not None or month_budget is not None:
        lines.append("")
        if week_budget is not None:
            remaining = max(week_budget - week_total, 0.0)
            lines.append(f"Remaining weekly budget: {fmt_money(remaining)}")
        if month_budget is not None:
            remaining = max(month_budget - month_total, 0.0)
            lines.append(f"Remaining monthly budget: {fmt_money(remaining)}")

    return "\n".join(lines)
