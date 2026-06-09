"""Screenshot ingestion: OCR + AI extraction of expenses."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import Message

from app.ai import generate_financial_insights, parse_transactions
from app.analytics import AnalyticsService
from app.models import BudgetPeriod, User
from app.ocr import extract_text
from app.services import BudgetService, ExpenseService
from app.utils.formatting import format_added_summary

logger = logging.getLogger(__name__)

router = Router(name="screenshots")


@router.message(F.photo)
async def handle_photo(
    message: Message,
    user: User,
    expense_service: ExpenseService,
    budget_service: BudgetService,
) -> None:
    status = await message.answer("📸 Reading your screenshot…")

    # Download the highest-resolution photo.
    photo = message.photo[-1]
    buffer = await message.bot.download(photo)
    image_bytes = buffer.read()

    # OCR.
    try:
        text = await extract_text(image_bytes)
    except Exception:
        logger.exception("OCR failed")
        await status.edit_text(
            "⚠️ I couldn't read that image. Make sure OCR is installed "
            "(tesseract) and the screenshot is clear."
        )
        return

    if not text:
        await status.edit_text(
            "🤔 I couldn't read any text from that screenshot. Try a clearer image."
        )
        return

    # AI extraction.
    await status.edit_text("🧠 Extracting transactions…")
    parsed = await parse_transactions(text)

    if not parsed:
        await status.edit_text(
            "🤔 I didn't find any expenses in that screenshot.\n"
            "Send a clearer image of the transactions list."
        )
        return

    created = await expense_service.add_many(
        user.id,
        parsed,
        default_currency=user.currency,
        raw_text=text,
    )

    await status.edit_text(format_added_summary(created))

    # Follow-up: quick weekly budget insight if a budget exists.
    analytics = AnalyticsService(expense_service, budget_service)
    metrics = await analytics.build_metrics(user, BudgetPeriod.WEEK)
    if "budget" in metrics:
        insight = await generate_financial_insights(metrics)
        await message.answer(f"🧠 <b>Quick take</b>\n\n{insight}")
