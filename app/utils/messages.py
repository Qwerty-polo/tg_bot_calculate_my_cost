"""Send bounded HTML messages without cutting tags or transaction lines."""

from aiogram.types import InlineKeyboardMarkup, Message


def message_pages(text: str, limit: int = 3500) -> list[str]:
    pages = []
    current = ""
    for line in text.splitlines():
        candidate = f"{current}\n{line}" if current else line
        if len(candidate.encode("utf-16-le")) // 2 > limit:
            if not current:
                raise ValueError("A message line exceeds the page limit")
            pages.append(current)
            current = line
        else:
            current = candidate
    if current:
        pages.append(current)
    return pages


async def send_pages(
    message: Message, text: str, *, edit_first: bool = False,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    pages = message_pages(text)
    for index, page in enumerate(pages):
        markup = reply_markup if index == len(pages) - 1 else None
        if index == 0 and edit_first:
            await message.edit_text(page, reply_markup=markup)
        else:
            await message.answer(page, reply_markup=markup)
