"""Human-friendly message formatting (HTML parse mode)."""

from __future__ import annotations

from collections.abc import Sequence
from html import escape

from app.models import Expense, ExpenseCategory


def fmt_money(amount: float, currency: str) -> str:
    return f"{amount:,.2f} {currency}".replace(",", " ")


def progress_bar(pct: float, width: int = 10) -> str:
    """A unicode progress bar, clamped to [0, 100]."""
    pct = max(0.0, min(pct, 100.0))
    filled = round(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


def format_expense_line(expense: Expense) -> str:
    cat = expense.category if isinstance(expense.category, ExpenseCategory) else (
        ExpenseCategory.from_value(str(expense.category))
    )
    merchant = escape(expense.merchant or expense.description or "Purchase")
    when = expense.occurred_at.strftime("%d.%m %H:%M")
    return (
        f"{cat.emoji} <b>{fmt_money(float(expense.amount), expense.currency)}</b> "
        f"— {merchant} <i>({when})</i>"
    )


def format_expense_list(expenses: Sequence[Expense], *, title: str) -> str:
    if not expenses:
        return f"<b>{escape(title)}</b>\n\nNo expenses recorded yet."
    lines = [f"<b>{escape(title)}</b>", ""]
    total = 0.0
    currency = expenses[0].currency
    for expense in expenses:
        lines.append(format_expense_line(expense))
        total += float(expense.amount)
    lines.append("")
    lines.append(f"<b>Total:</b> {fmt_money(total, currency)} • {len(expenses)} item(s)")
    return "\n".join(lines)


def format_added_summary(expenses: Sequence[Expense]) -> str:
    if not expenses:
        return (
            "🤔 I couldn't find any expenses in that screenshot.\n"
            "Try a clearer image of the transactions list."
        )
    currency = expenses[0].currency
    total = sum(float(e.amount) for e in expenses)
    header = f"✅ Added <b>{len(expenses)}</b> expense(s) • {fmt_money(total, currency)}"
    lines = [header, ""]
    lines.extend(format_expense_line(e) for e in expenses)
    return "\n".join(lines)


def format_categories(metrics: dict) -> str:
    categories = metrics.get("categories") or []
    currency = metrics.get("currency", "")
    if not categories:
        return "📊 <b>Categories</b>\n\nNo expenses recorded for this period yet."
    lines = [f"📊 <b>Spending by category ({escape(str(metrics.get('period')))})</b>", ""]
    for cat in categories:
        bar = progress_bar(cat["pct"])
        lines.append(
            f"{cat['emoji']} <b>{escape(cat['name'])}</b>\n"
            f"   {bar} {cat['pct']:.0f}% • {fmt_money(cat['amount'], currency)}"
        )
    lines.append("")
    lines.append(f"<b>Total:</b> {fmt_money(metrics.get('total_spent', 0.0), currency)}")
    return "\n".join(lines)


def format_budget_status(metrics: dict) -> str:
    currency = metrics.get("currency", "")
    period = escape(str(metrics.get("period")))
    lines = [f"🎯 <b>Budget status ({period})</b>", ""]
    if "budget" not in metrics:
        lines.append(
            "No budget set for this period.\n"
            "Use /set_week_budget or /set_month_budget to add one."
        )
        lines.append("")
        lines.append(
            f"Spent so far: <b>{fmt_money(metrics.get('total_spent', 0.0), currency)}</b>"
        )
        return "\n".join(lines)

    used = metrics.get("budget_used_pct", 0.0)
    lines.append(f"{progress_bar(used)} <b>{used:.0f}%</b>")
    lines.append("")
    lines.append(f"Budget: <b>{fmt_money(metrics['budget'], currency)}</b>")
    lines.append(f"Spent: <b>{fmt_money(metrics.get('total_spent', 0.0), currency)}</b>")
    lines.append(
        f"Remaining: <b>{fmt_money(metrics.get('budget_remaining', 0.0), currency)}</b>"
    )
    forecast = metrics.get("days_until_overspend")
    if forecast is not None:
        lines.append("")
        lines.append(
            f"⚠️ At this pace you may exceed your budget in ~{forecast} day(s)."
        )
    return "\n".join(lines)


def format_period_header(metrics: dict) -> str:
    currency = metrics.get("currency", "")
    period = escape(str(metrics.get("period")))
    total = metrics.get("total_spent", 0.0)
    count = metrics.get("expense_count", 0)
    return (
        f"🧾 <b>{period.capitalize()} summary</b>\n"
        f"Spent <b>{fmt_money(total, currency)}</b> across {count} expense(s)."
    )
