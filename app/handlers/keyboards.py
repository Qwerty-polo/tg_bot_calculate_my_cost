"""Shared keyboards / button labels for the main menu."""

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# Main-menu button label (matched verbatim by the reset handler).
RESET_BUTTON = "🗑 Reset Statistics"

# Callback data for the reset confirmation dialog.
RESET_CONFIRM = "reset:confirm"
RESET_CANCEL = "reset:cancel"


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Persistent reply keyboard shown under the chat input."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=RESET_BUTTON)]],
        resize_keyboard=True,
        input_field_placeholder="Send a screenshot or pick an action…",
    )


def reset_confirm_keyboard() -> InlineKeyboardMarkup:
    """Inline Yes/Cancel keyboard for the destructive reset action."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Yes, delete everything", callback_data=RESET_CONFIRM
                ),
                InlineKeyboardButton(text="❌ Cancel", callback_data=RESET_CANCEL),
            ]
        ]
    )
