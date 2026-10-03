"""Screenshot ingestion: OCR + AI extraction of expenses."""

from __future__ import annotations

import logging
from datetime import datetime
from hashlib import sha256
from secrets import token_hex

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.ai import looks_like_income, parse_transactions
from app.ai.schemas import ParsedExpenseList
from app.handlers.keyboards import action_keyboard
from app.models import User
from app.ocr import extract_text
from app.services import ExpenseService
from app.utils.formatting import format_added_summary, format_preview
from app.utils.messages import send_pages
from app.utils.money import UnsupportedCurrencyError

logger = logging.getLogger(__name__)

router = Router(name="screenshots")


class UploadStates(StatesGroup):
    review = State()


@router.message(F.photo)
async def handle_photo(
    message: Message,
    user: User,
    expense_service: ExpenseService,
    state: FSMContext,
) -> None:
    if await state.get_state() is not None:
        await message.answer("Finish your pending action, or use /cancel before sending a photo.")
        return
    received_at = message.date
    status = await message.answer("📸 Reading your screenshot…")

    # Download the highest-resolution photo.
    photo = message.photo[-1]
    buffer = await message.bot.download(photo)
    image_bytes = buffer.read()
    digest = sha256(image_bytes).hexdigest()
    async with expense_service.session.begin():
        duplicate = await expense_service.has_upload(user.id, digest)
    if duplicate:
        await status.edit_text("This screenshot has already been recorded. Nothing was added.")
        return

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
    try:
        parsed = await parse_transactions(text)
    except UnsupportedCurrencyError:
        await status.edit_text(
            "Only UAH expenses are supported. This screenshot contains a foreign or unclear "
            "currency. Nothing was saved. Please send a screenshot with explicit UAH amounts."
        )
        return
    parsed = [item for item in parsed if not looks_like_income(item.merchant)]

    if not parsed:
        await status.edit_text(
            "🤔 I didn't find any expenses in that screenshot.\n"
            "Send a clearer image with explicit UAH amounts."
        )
        return

    if len(parsed) > 100:
        await status.edit_text("Please send a smaller screenshot with at most 100 expenses.")
        return
    token = token_hex(8)
    await state.set_state(UploadStates.review)
    await state.set_data({
        "token": token, "digest": digest, "raw_text": text,
        "parsed": [item.model_dump(mode="json") for item in parsed],
        "received_at": received_at.isoformat(), "timezone": user.timezone,
    })
    await send_pages(
        status, format_preview(parsed, received_at, user.timezone), edit_first=True,
        reply_markup=action_keyboard("upload", token, "Confirm expenses"),
    )


@router.callback_query(F.data.startswith("upload:"))
async def on_upload_action(
    callback: CallbackQuery, user: User, expense_service: ExpenseService, state: FSMContext
) -> None:
    parts = (callback.data or "").split(":")
    pending = await state.get_data()
    if (
        len(parts) != 3 or parts[1] not in {"confirm", "cancel"}
        or await state.get_state() != UploadStates.review.state
        or pending.get("token") != parts[2]
    ):
        await callback.answer("This preview is no longer active. Send the screenshot again.")
        return
    if parts[1] == "cancel":
        await state.clear()
        if isinstance(callback.message, Message):
            await callback.message.edit_text("Cancelled. No expenses were saved.")
        await callback.answer()
        return
    parsed = ParsedExpenseList.model_validate({"expenses": pending["parsed"]}).expenses
    async with expense_service.session.begin():
        created = await expense_service.add_upload(
            user.id, pending["digest"], parsed, raw_text=pending["raw_text"],
            fallback_dt=datetime.fromisoformat(pending["received_at"]),
            timezone=pending["timezone"],
        )
    await state.clear()
    if isinstance(callback.message, Message):
        text = (
            "This screenshot has already been recorded. Nothing was added."
            if created is None else format_added_summary(created, pending["timezone"])
        )
        await send_pages(callback.message, text, edit_first=True)
    await callback.answer("Done")
