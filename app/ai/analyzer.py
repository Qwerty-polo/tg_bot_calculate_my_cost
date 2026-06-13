"""High-level AI operations: transaction parsing and financial analysis.

All functions degrade gracefully when no Gemini key is configured:
- :func:`parse_transactions` falls back to a heuristic regex parser.
- The insight / recommendation helpers fall back to deterministic templates.

The bot is UAH-only, so every parsed expense is stored in hryvnia regardless of
any currency symbol that appears in the screenshot.
"""

from __future__ import annotations

import json
import logging
import re

from app.ai import prompts
from app.ai.schemas import ParsedExpense, ParsedExpenseList
from app.config import CURRENCY_SYMBOL, settings

logger = logging.getLogger(__name__)


async def parse_transactions(ocr_text: str) -> list[ParsedExpense]:
    """Convert raw OCR text into a list of structured expenses."""
    text = (ocr_text or "").strip()
    if not text:
        return []

    if settings.has_llm:
        try:
            return await _parse_with_ai(text)
        except Exception:  # noqa: BLE001 - fall back, never crash the handler
            logger.exception("AI transaction parsing failed; using heuristic fallback")

    return _heuristic_parse(text)


async def _parse_with_ai(ocr_text: str) -> list[ParsedExpense]:
    from app.ai.client import chat_json

    raw = await chat_json(
        prompts.TRANSACTION_SYSTEM_PROMPT,
        prompts.TRANSACTION_USER_PROMPT.format(ocr_text=ocr_text),
    )
    data = json.loads(raw)
    parsed = ParsedExpenseList.model_validate(data)
    return parsed.expenses


# ─── Heuristic fallback parser ──────────────────────────────────────────────

_AMOUNT_RE = re.compile(
    r"(?P<amount>\d{1,3}(?:[ \u00a0]\d{3})+(?:[.,]\d{2})?|\d+(?:[.,]\d{2})?)\s*"
    r"(?:грн|UAH|₴|USD|\$|EUR|€)?",
    re.IGNORECASE,
)


def _heuristic_parse(text: str) -> list[ParsedExpense]:
    """A best-effort parser used when the AI is unavailable.

    It scans each line for an amount and treats the surrounding words as the
    merchant. This is intentionally conservative and only meant as a fallback.
    """
    expenses: list[ParsedExpense] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = _AMOUNT_RE.search(line)
        if not match:
            continue
        amount_str = match.group("amount").replace("\u00a0", "").replace(" ", "")
        amount_str = amount_str.replace(",", ".")
        try:
            amount = float(amount_str)
        except ValueError:
            continue
        if amount <= 0:
            continue
        merchant = _AMOUNT_RE.sub("", line).strip(" -—:•\t") or None
        expenses.append(
            ParsedExpense(
                amount=amount,
                currency=settings.default_currency,
                merchant=merchant,
                description=merchant,
            )
        )
    return expenses


# ─── Financial analysis narratives ──────────────────────────────────────────


async def generate_financial_insights(metrics: dict) -> str:
    """Generate a human-readable financial analysis from computed metrics."""
    if settings.has_llm:
        try:
            from app.ai.client import chat_text

            return await chat_text(
                prompts.INSIGHTS_SYSTEM_PROMPT,
                prompts.INSIGHTS_USER_PROMPT.format(
                    metrics_json=json.dumps(metrics, ensure_ascii=False, default=str)
                ),
            )
        except Exception:  # noqa: BLE001
            logger.exception("AI insight generation failed; using template fallback")
    return _template_insights(metrics)


async def generate_saving_recommendations(metrics: dict) -> str:
    """Generate AI saving recommendations from computed metrics."""
    if settings.has_llm:
        try:
            from app.ai.client import chat_text

            return await chat_text(
                prompts.SAVINGS_SYSTEM_PROMPT,
                prompts.SAVINGS_USER_PROMPT.format(
                    metrics_json=json.dumps(metrics, ensure_ascii=False, default=str)
                ),
            )
        except Exception:  # noqa: BLE001
            logger.exception("AI savings generation failed; using template fallback")
    return _template_savings(metrics)


def _template_insights(metrics: dict) -> str:
    currency = CURRENCY_SYMBOL
    lines: list[str] = []
    pct = metrics.get("budget_used_pct")
    if pct is not None:
        lines.append(f"💰 You already spent {pct:.0f}% of your {metrics.get('period')} budget.")
    remaining = metrics.get("budget_remaining")
    if remaining is not None:
        lines.append(f"🧮 Remaining balance: {remaining:.2f} {currency}.")
    top = metrics.get("top_category")
    if top:
        lines.append(
            f"📊 Most of your money went to {top['name']} ({top['pct']:.0f}%)."
        )
    biggest = metrics.get("biggest_expense")
    if biggest:
        lines.append(
            f"🏷️ Your biggest expense was {biggest.get('merchant') or 'a purchase'} "
            f"— {biggest['amount']:.2f} {currency}."
        )
    avg = metrics.get("daily_average")
    if avg is not None:
        lines.append(f"📅 Daily average spending: {avg:.2f} {currency}.")
    forecast = metrics.get("days_until_overspend")
    if forecast is not None:
        lines.append(
            f"⚠️ At this pace you may exceed your budget in ~{forecast} day(s)."
        )
    if not lines:
        lines.append("No expenses recorded yet for this period.")
    return "\n".join(lines)


def _template_savings(metrics: dict) -> str:
    currency = CURRENCY_SYMBOL
    lines = ["💡 *Saving ideas:*"]
    top = metrics.get("top_category")
    if top:
        lines.append(
            f"• {top['name']} is your biggest category ({top['pct']:.0f}%). "
            "Setting a sub-limit there could free up cash."
        )
    subs = metrics.get("subscriptions") or []
    if subs:
        total = sum(s.get("amount", 0) for s in subs)
        lines.append(
            f"• You have {len(subs)} recurring subscription(s) totalling "
            f"~{total:.2f} {currency}. Cancel the ones you don't use."
        )
    if len(lines) == 1:
        lines.append("• Keep logging expenses to unlock tailored recommendations.")
    return "\n".join(lines)
