"""Review, deletion, timezone and data validation regression scenarios."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from app.ai.analyzer import parse_transactions
from app.ai.schemas import ParsedExpense
from app.config import settings
from app.handlers import screenshots
from app.handlers.screenshots import UploadStates
from app.models import Budget, Expense, Upload, User
from app.services import ExpenseService, UserService
from app.utils.formatting import format_preview, format_today
from app.utils.messages import message_pages
from app.utils.money import UnsupportedCurrencyError
from app.utils.timeframe import as_utc, day_range, month_range, week_range
from tests.test_bot_reliability import app

__all__ = ["app"]


async def count_rows(app, model):
    async with app.factory() as session:
        return await session.scalar(select(func.count()).select_from(model))


async def test_preview_does_not_persist_expenses_or_upload_marker(app):
    await app.send(photo=True)
    assert await app.state.get_state() == UploadStates.review.state
    assert "Nothing is saved yet" in app.transport.requests[-1].text
    assert "date missing; upload time" in app.transport.requests[-1].text
    for model in (Expense, Upload):
        assert await count_rows(app, model) == 0


async def test_confirm_twice_only_saves_once(app):
    await app.send(photo=True)
    pending = await app.state.get_data()
    callback = f"upload:confirm:{pending['token']}"
    await asyncio.gather(app.send(callback=callback), app.send(callback=callback))
    assert await count_rows(app, Expense) == 1
    assert await count_rows(app, Upload) == 1
    assert await app.state.get_state() is None


@pytest.mark.parametrize("cancel", ["button", "command", "reset"])
async def test_cancelled_preview_cannot_be_confirmed(app, cancel):
    await app.send(photo=True)
    token = (await app.state.get_data())["token"]
    if cancel == "button":
        await app.send(callback=f"upload:cancel:{token}")
    elif cancel == "reset":
        await app.send(callback=True)
    else:
        await app.send("/cancel")
    await app.send(callback=f"upload:confirm:{token}")
    assert await count_rows(app, Expense) == 0
    assert "no longer active" in app.transport.requests[-1].text


async def test_foreign_user_and_stale_token_cannot_confirm_preview(app):
    await app.send(photo=True)
    token = (await app.state.get_data())["token"]
    await app.send(callback=f"upload:confirm:{token}", user_id=2)
    await app.send(callback="upload:confirm:wrong-token")
    assert await count_rows(app, Expense) == 0
    await app.confirm_upload()
    assert await count_rows(app, Expense) == 1


async def test_second_photo_does_not_replace_pending_preview(app):
    await app.send(photo=True)
    pending = await app.state.get_data()
    await app.send(photo=True)
    assert await app.state.get_data() == pending
    assert "pending action" in app.transport.requests[-1].text


async def test_exact_duplicate_is_detected_before_ocr(app, monkeypatch):
    await app.save_photo()
    ocr = AsyncMock(side_effect=AssertionError("OCR should not run"))
    monkeypatch.setattr(screenshots, "extract_text", ocr)
    await app.send(photo=True)
    ocr.assert_not_awaited()


async def test_missing_date_uses_upload_time_even_if_confirmation_is_later(app):
    await app.send(photo=True)
    pending = await app.state.get_data()
    pending["received_at"] = "2026-09-01T23:30:00+00:00"
    await app.state.set_data(pending)
    await app.confirm_upload()
    async with app.factory() as session:
        expense = await session.scalar(select(Expense))
        assert expense.occurred_at == datetime(2026, 9, 1, 23, 30)


async def test_timezone_change_does_not_change_the_date_in_an_open_preview(app, monkeypatch):
    monkeypatch.setattr(screenshots, "parse_transactions", AsyncMock(return_value=[
        ParsedExpense(amount=50, occurred_at=datetime(2026, 1, 1, 0, 30)),
    ]))
    await app.send(photo=True)
    await app.send("/timezone America/New_York")
    await app.confirm_upload()
    async with app.factory() as session:
        expense = await session.scalar(select(Expense))
        assert expense.occurred_at == datetime(2025, 12, 31, 22, 30)
        assert (await session.scalar(select(User))).timezone == "America/New_York"


async def test_foreign_currency_returns_explanation_and_saves_nothing(app, monkeypatch):
    monkeypatch.setattr(screenshots, "parse_transactions", AsyncMock(
        side_effect=UnsupportedCurrencyError()
    ))
    await app.send(photo=True)
    assert "Only UAH" in app.transport.requests[-1].text
    assert await count_rows(app, Expense) == 0
    assert await app.state.get_state() is None


async def test_delete_requires_confirmation_and_preserves_budget_and_fingerprint(app):
    await app.save_photo()
    await app.send("/set_week_budget 5000")
    await app.send("/delete 1")
    token = (await app.state.get_data())["token"]
    assert await count_rows(app, Expense) == 1
    await app.send(callback=f"delete:confirm:{token}")
    assert await count_rows(app, Expense) == 0
    assert await count_rows(app, Budget) == 1
    assert await count_rows(app, Upload) == 1
    await app.send(photo=True)
    assert "already been recorded" in app.transport.requests[-1].text


async def test_delete_cannot_remove_another_users_expense(app):
    await app.save_photo()
    await app.send("/delete 1", user_id=2)
    assert "not found" in app.transport.requests[-1].text
    await app.send("/delete 1")
    token = (await app.state.get_data())["token"]
    await app.send(callback=f"delete:confirm:{token}", user_id=2)
    assert await count_rows(app, Expense) == 1


async def test_cancel_delete_and_stale_button_leave_expense_intact(app):
    await app.save_photo()
    await app.send("/delete 1")
    token = (await app.state.get_data())["token"]
    await app.send(callback=f"delete:cancel:{token}")
    await app.send(callback=f"delete:confirm:{token}")
    assert await count_rows(app, Expense) == 1


async def test_failed_delete_commit_can_be_retried(app):
    await app.save_photo()
    await app.send("/delete 1")
    token = (await app.state.get_data())["token"]
    app.controls.fail_commit = True
    with pytest.raises(RuntimeError, match="Commit failed"):
        await app.send(callback=f"delete:confirm:{token}")
    assert await count_rows(app, Expense) == 1
    app.controls.fail_commit = False
    await app.send(callback=f"delete:confirm:{token}")
    assert await count_rows(app, Expense) == 0


@pytest.mark.parametrize("command", ["/expenses", "/delete 1", "/timezone Europe/Kyiv"])
async def test_new_financial_commands_stay_private(app, command):
    await app.send(command, chat_type="group")
    assert not app.sessions


async def test_history_has_dates_ids_pagination_and_user_isolation(app):
    await app.send("/start")
    async with app.factory() as session, session.begin():
        expenses = ExpenseService(session)
        await expenses.add_many(1, [ParsedExpense(amount=10, merchant="My cafe")] * 11)
        other = await UserService(session).get_or_create(2)
        await expenses.add_many(other.id, [ParsedExpense(amount=99, merchant="Private merchant")])
    await app.send("/expenses")
    text = app.transport.requests[-1].text
    assert text.count("My cafe") == 10
    assert "Private merchant" not in text
    assert "/expenses 2" in text
    await app.send("/expenses 2")
    assert app.transport.requests[-1].text.count("My cafe") == 1


async def test_service_rejects_currency_even_when_schema_is_bypassed(app):
    await app.send("/start")
    async with app.factory() as session:
        with pytest.raises(UnsupportedCurrencyError):
            async with session.begin():
                await ExpenseService(session).add_many(1, [
                    ParsedExpense.model_construct(amount=10, currency="USD"),
                ])


@pytest.mark.parametrize("currency", ["USD", "EUR", "UNKNOWN", None])
async def test_ai_foreign_or_unknown_currency_never_falls_back_to_uah(monkeypatch, currency):
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr("app.ai.client.chat_json", AsyncMock(return_value=json.dumps({
        "expenses": [{"amount": 100, "currency": currency}],
    })))
    with pytest.raises(UnsupportedCurrencyError):
        await parse_transactions("Cafe 100 UAH")


async def test_ai_validation_failure_does_not_log_private_fields(monkeypatch, caplog):
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr("app.ai.client.chat_json", AsyncMock(return_value=json.dumps({
        "expenses": [{"merchant": "PRIVATE_MERCHANT", "currency": "UAH"}],
    })))
    assert await parse_transactions("Cafe 100 UAH")
    assert "PRIVATE_MERCHANT" not in caplog.text


@pytest.mark.parametrize("day,hours", [(datetime(2025, 3, 30, 12), 23),
                                       (datetime(2025, 10, 26, 12), 25)])
def test_day_ranges_follow_daylight_saving(day, hours):
    start, end = day_range(day)
    assert end - start == timedelta(hours=hours)


def test_local_midnight_and_year_boundaries():
    now = datetime(2025, 12, 31, 23, 30, tzinfo=UTC)
    assert day_range(now) == (datetime(2025, 12, 31, 22), datetime(2026, 1, 1, 22))
    assert month_range(now) == (datetime(2025, 12, 31, 22), datetime(2026, 1, 31, 22))
    assert week_range(now)[0] == datetime(2025, 12, 28, 22)


def test_explicit_offset_is_preserved_and_naive_purchase_uses_local_zone():
    assert as_utc(datetime.fromisoformat("2026-01-01T00:30:00+03:00")) == datetime(
        2025, 12, 31, 21, 30
    )
    assert as_utc(datetime(2026, 1, 1, 0, 30), "Europe/Kyiv") == datetime(2025, 12, 31, 22, 30)


def test_long_history_and_preview_are_bounded_and_html_is_escaped():
    merchant = "<script>&" * 20
    expenses = [Expense(id=index + 1, amount=10, merchant=merchant,
                        occurred_at=datetime(2026, 1, 1, 12)) for index in range(100)]
    for text in (
        format_today(expenses),
        format_preview([ParsedExpense(amount=10, merchant=merchant)] * 100,
                       datetime(2026, 1, 1, 12, tzinfo=UTC), "Europe/Kyiv"),
    ):
        pages = message_pages(text)
        assert len(pages) > 1
        assert all(len(page.encode("utf-16-le")) // 2 <= 3500 for page in pages)
        assert "<script>" not in text
