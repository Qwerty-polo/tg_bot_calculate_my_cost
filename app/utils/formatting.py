"""Human-friendly message formatting (HTML parse mode)."""

from __future__ import annotations

from collections.abc import Sequence
from html import escape

from app.config import CURRENCY_SYMBOL
from app.models import Expense


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


def format_expense_line(expense: Expense) -> str:
    merchant = escape(expense.merchant or "Purchase")
    when = expense.occurred_at.strftime("%H:%M")
    return f"{when} — {merchant} {fmt_money(float(expense.amount))}"


def format_today(expenses: Sequence[Expense]) -> str:
    if not expenses:
        return "Today's expenses:\n\nNothing logged yet. Send a screenshot. 📸"
    lines = ["<b>Today's expenses:</b>", ""]
    total = 0.0
    for expense in expenses:
        lines.append(format_expense_line(expense))
        total += float(expense.amount)
    lines.append("")
    lines.append(f"<b>Total today:</b> {fmt_money(total)}")
    return "\n".join(lines)


def format_added_summary(expenses: Sequence[Expense]) -> str:
    if not expenses:
        return (
            "🤔 I couldn't find any expenses in that screenshot.\n"
            "Try a clearer image of the transactions list."
        )
    total = sum(float(e.amount) for e in expenses)
    lines = [f"✅ Added <b>{len(expenses)}</b> expense(s):", ""]
    lines.extend(format_expense_line(e) for e in expenses)
    lines.append("")
    lines.append(f"<b>Total:</b> {fmt_money(total)}")
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
