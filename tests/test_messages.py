"""Paginated replies keep all content and attach actions to the final page."""

from unittest.mock import AsyncMock, Mock, call

import pytest

from app.handlers.keyboards import action_keyboard
from app.utils.messages import send_pages


@pytest.mark.parametrize("edit_first", [False, True])
async def test_send_pages_preserves_content_and_final_page_actions(edit_first):
    message = Mock(answer=AsyncMock(), edit_text=AsyncMock())
    markup = action_keyboard("upload", "test-token", "Confirm expenses")
    # Each complete HTML line fits on a page, but two exceed the UTF-16 limit.
    lines = [f"<b>{index}: {'🍵' * 900}</b>" for index in range(3)]

    await send_pages(message, "\n".join(lines), edit_first=edit_first, reply_markup=markup)

    expected = [
        call(line, reply_markup=markup if index == len(lines) - 1 else None)
        for index, line in enumerate(lines)
    ]
    if edit_first:
        message.edit_text.assert_awaited_once_with(lines[0], reply_markup=None)
        assert message.answer.await_args_list == expected[1:]
    else:
        message.edit_text.assert_not_awaited()
        assert message.answer.await_args_list == expected
