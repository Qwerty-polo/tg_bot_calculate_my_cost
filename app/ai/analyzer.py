"""Transaction parsing: OCR text -> structured expenses.

:func:`parse_transactions` uses Gemini when a key is configured and falls back
to a heuristic regex parser otherwise. The bot is UAH-only, so every parsed
expense is stored in hryvnia regardless of any currency symbol in the
screenshot.
"""

from __future__ import annotations

import json
import logging
import re

from app.ai import prompts
from app.ai.schemas import ParsedExpense, ParsedExpenseList
from app.config import settings

logger = logging.getLogger(__name__)

# Words that mark a line as INCOMING money (never an expense). Used by the
# heuristic parser to skip such lines.
_INCOME_KEYWORDS = (
    "поповнення",
    "зарахування",
    "переказ від",
    "надходження",
    "кешбек",
    "кешбэк",
    "зарплата",
    "пенсія",
    "пенсия",
    "виплата",
    "cashback",
    "refund",
    "salary",
    "deposit",
)


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
    merchant. Incoming-money lines are skipped. This is intentionally
    conservative and only meant as a fallback.
    """
    expenses: list[ParsedExpense] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if looks_like_income(line):
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
            )
        )
    return expenses


def looks_like_income(text: str | None) -> bool:
    """True if the text looks like money RECEIVED rather than spent."""
    if not text:
        return False
    lowered = text.lower()
    return any(keyword in lowered for keyword in _INCOME_KEYWORDS)
