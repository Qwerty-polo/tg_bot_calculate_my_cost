"""Exercise routing and transaction boundaries without Telegram/OCR/AI network calls."""

import asyncio
import copy
import io
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendMessage
from aiogram.types import CallbackQuery, Chat, Message, PhotoSize, Update, User
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.ai.schemas import ParsedExpense
from app.database.base import Base
from app.handlers import budgets, common, reset, screenshots, stats
from app.handlers.keyboards import RESET_CONFIRM
from app.middlewares.database import ServicesMiddleware
from app.middlewares.logging import LoggingMiddleware
from app.models import Budget, Expense, Upload
from app.services import ExpenseService


class TelegramStub(BaseSession):
    def __init__(self, sessions):
        super().__init__()
        self.sessions = sessions
        self.requests = []
        self.fail_success = False

    async def close(self):
        pass

    async def make_request(self, bot, method, timeout=None):
        assert all(not session.in_transaction() for session in self.sessions)
        self.requests.append(method)
        text = getattr(method, "text", "")
        if self.fail_success and any(
            word in text for word in ("Added", "budget is set", "complete")
        ):
            raise RuntimeError("Telegram unavailable")
        if isinstance(method, AnswerCallbackQuery):
            return True
        assert isinstance(method, SendMessage | EditMessageText)
        return Message(
            message_id=len(self.requests), date=datetime.now(UTC), text=method.text,
            chat=Chat(id=method.chat_id, type="private"),
        ).as_(bot)

    async def stream_content(self, *args, **kwargs):
        yield b""


@pytest_asyncio.fixture
async def app(monkeypatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = []
    controls = SimpleNamespace(fail_commit=False)

    class TrackedSession(AsyncSession):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            sessions.append(self)
            commits = 0

            def before_commit(session):
                nonlocal commits
                commits += 1
                # Fail the financial commit, not middleware's user setup.
                if controls.fail_commit and commits > 1:
                    raise RuntimeError("Commit failed")

            event.listen(self.sync_session, "before_commit", before_commit)

    factory = async_sessionmaker(engine, class_=TrackedSession, expire_on_commit=False)
    monkeypatch.setattr("app.middlewares.database.create_session_factory", lambda: factory)
    monkeypatch.setattr(
        "app.middlewares.database.settings", SimpleNamespace(allowed_user_id_set=set())
    )
    transport = TelegramStub(sessions)
    bot = Bot("123456:TEST_TOKEN", session=transport)
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.message.outer_middleware(LoggingMiddleware())
    dispatcher.message.middleware(ServicesMiddleware())
    dispatcher.callback_query.middleware(ServicesMiddleware())
    for module in (common, reset, budgets, stats, screenshots):
        dispatcher.include_router(copy.deepcopy(module.router))

    async def send(text=None, *, chat_type="private", photo=False, callback=False):
        message = Message(
            message_id=1, date=datetime.now(UTC), chat=Chat(id=1, type=chat_type),
            from_user=User(id=1, is_bot=False, first_name="Tester"), text=text,
            photo=[PhotoSize(file_id="photo", file_unique_id="unique", width=10, height=10)]
            if photo else None,
        )
        if callback:
            update = Update(update_id=1, callback_query=CallbackQuery(
                id="cb", from_user=message.from_user, chat_instance="test",
                message=message, data=RESET_CONFIRM,
            ))
        else:
            update = Update(update_id=1, message=message)
        return await dispatcher.feed_update(bot, update)

    async def download(*args, **kwargs):
        assert all(not session.in_transaction() for session in sessions)
        return io.BytesIO(b"same photo bytes")

    async def ocr(*args):
        assert all(not session.in_transaction() for session in sessions)
        return "Cafe 50 UAH"

    async def parse(*args):
        assert all(not session.in_transaction() for session in sessions)
        return [ParsedExpense(amount=50, merchant="Cafe")]

    monkeypatch.setattr(bot, "download", download)
    monkeypatch.setattr(screenshots, "extract_text", ocr)
    monkeypatch.setattr(screenshots, "parse_transactions", parse)
    state = dispatcher.fsm.get_context(bot=bot, chat_id=1, user_id=1)
    yield SimpleNamespace(send=send, factory=factory, transport=transport, state=state,
                          controls=controls, sessions=sessions)
    await dispatcher.storage.close()
    await bot.session.close()
    await engine.dispose()


@pytest.mark.parametrize("command", ["/today", "/stats", "/help", "/unknown"])
async def test_pending_budget_does_not_consume_commands(app, command):
    await app.send("/set_week_budget")
    app.transport.requests.clear()
    await app.send(command)
    assert not any("positive number" in getattr(r, "text", "") for r in app.transport.requests)
    if command != "/unknown":
        assert app.transport.requests


@pytest.mark.parametrize("command", ["/start", "/cancel", "/set_month_budget 20000"])
async def test_commands_clear_stale_budget_state(app, command):
    await app.send("/set_week_budget")
    assert await app.state.get_state() is not None
    await app.send(command)
    assert await app.state.get_state() is None


@pytest.mark.parametrize("chat_type", ["group", "supergroup"])
@pytest.mark.parametrize(
    "command", ["/today", "/stats", "/set_week_budget 5000", "/set_month_budget"]
)
async def test_financial_commands_in_groups_do_not_touch_database(app, command, chat_type):
    await app.send(command, chat_type=chat_type)
    assert not app.sessions
    assert "private chat" in app.transport.requests[-1].text
    assert "5000" not in app.transport.requests[-1].text


async def test_group_photo_and_reset_are_private(app):
    await app.send(photo=True, chat_type="group")
    await app.send(callback=True, chat_type="group")
    assert not app.sessions
    assert "private chat" in app.transport.requests[-1].text


@pytest.mark.parametrize("command", ["/start", "/help", "/cancel"])
async def test_basic_commands_work_in_groups(app, command):
    await app.send(command, chat_type="group")
    assert app.transport.requests
    assert not app.sessions


@pytest.mark.parametrize("photo", [False, True])
async def test_telegram_failure_does_not_rollback_committed_financial_data(app, photo):
    app.transport.fail_success = True
    with pytest.raises(RuntimeError, match="Telegram unavailable"):
        await app.send(None if photo else "/set_week_budget 5000", photo=photo)
    async with app.factory() as session:
        model = Expense if photo else Budget
        assert await session.scalar(select(func.count()).select_from(model)) == 1


async def test_commit_failure_does_not_send_success_or_clear_pending_input(app):
    await app.send("/set_week_budget")
    app.transport.requests.clear()
    app.controls.fail_commit = True
    with pytest.raises(RuntimeError, match="Commit failed"):
        await app.send("5000")
    assert not app.transport.requests
    assert await app.state.get_state() == budgets.BudgetStates.waiting_for_week.state
    async with app.factory() as session:
        assert await session.scalar(select(func.count()).select_from(Budget)) == 0


async def test_exact_reupload_does_not_add_expenses_and_reset_allows_reupload(app):
    await app.send(photo=True)
    await app.send(photo=True)
    assert "already been recorded" in app.transport.requests[-1].text
    async with app.factory() as session:
        assert await session.scalar(select(func.count()).select_from(Expense)) == 1
        assert await session.scalar(select(func.count()).select_from(Upload)) == 1
    await app.send(callback=True)
    await app.send(photo=True)
    assert "Added" in app.transport.requests[-1].text


async def test_failed_upload_commit_leaves_no_expenses_or_marker_and_can_retry(app):
    app.controls.fail_commit = True
    with pytest.raises(RuntimeError, match="Commit failed"):
        await app.send(photo=True)
    assert not any("Added" in getattr(r, "text", "") for r in app.transport.requests)
    async with app.factory() as session:
        for model in (Expense, Upload):
            assert await session.scalar(select(func.count()).select_from(model)) == 0
    app.controls.fail_commit = False
    await app.send(photo=True)
    assert "Added" in app.transport.requests[-1].text


async def test_reset_reply_failure_does_not_undo_reset(app):
    await app.send(photo=True)
    await app.send("/set_week_budget 5000")
    app.transport.fail_success = True
    with pytest.raises(RuntimeError, match="Telegram unavailable"):
        await app.send(callback=True)
    async with app.factory() as session:
        for model in (Expense, Budget, Upload):
            assert await session.scalar(select(func.count()).select_from(model)) == 0


async def test_logging_omits_message_body_and_profile(app, caplog):
    with caplog.at_level("INFO", logger="bot.updates"):
        await app.send("/set_week_budget 123456.78")
    assert "Incoming message" in caplog.text
    assert "123456.78" not in caplog.text
    assert "Tester" not in caplog.text


async def test_user_setup_commit_failure_prevents_dispatch(app, monkeypatch):
    handler = AsyncMock()
    session = AsyncMock()
    session.begin = lambda: FailingTransaction()
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = session
    monkeypatch.setattr("app.middlewares.database.create_session_factory", lambda: factory)
    monkeypatch.setattr("app.middlewares.database.UserService.get_or_create", AsyncMock())
    message = Message(message_id=1, date=datetime.now(UTC), chat=Chat(id=1, type="private"))
    with pytest.raises(RuntimeError, match="Commit failed"):
        await ServicesMiddleware()(handler, message, {
            "event_from_user": User(id=1, is_bot=False, first_name="Test"),
        })
    handler.assert_not_awaited()


class FailingTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        raise RuntimeError("Commit failed")


async def test_concurrent_duplicate_uploads_only_persist_once(app):
    await app.send("/start")

    async def save():
        async with app.factory() as session, session.begin():
            return await ExpenseService(session).add_upload(
                1, "a" * 64, [ParsedExpense(amount=50)], raw_text="Cafe 50 UAH"
            )

    results = await asyncio.gather(save(), save())
    assert sum(result is None for result in results) == 1
    async with app.factory() as session:
        assert await session.scalar(select(func.count()).select_from(Expense)) == 1


async def test_upload_marker_rolls_back_on_failure_and_is_scoped_to_user(app):
    await app.send("/start")
    async with app.factory() as session:
        with pytest.raises(RuntimeError, match="abort"):
            async with session.begin():
                await ExpenseService(session).add_upload(
                    1, "b" * 64, [ParsedExpense(amount=50)], raw_text="Cafe 50 UAH"
                )
                raise RuntimeError("abort")
        async with session.begin():
            assert await session.scalar(select(func.count()).select_from(Upload)) == 0
            assert await session.scalar(select(func.count()).select_from(Expense)) == 0
        async with session.begin():
            from app.services import UserService

            second_user = await UserService(session).get_or_create(2)
            for user_id in (1, second_user.id):
                assert await ExpenseService(session).add_upload(
                    user_id, "b" * 64, [ParsedExpense(amount=50)], raw_text="Cafe 50 UAH"
                ) is not None


async def test_invalid_amount_cannot_bypass_service_validation(app):
    await app.send("/start")
    from app.models import BudgetPeriod
    from app.services import BudgetService

    async with app.factory() as session:
        for amount in (0, -1, float("nan"), float("inf")):
            with pytest.raises(ValueError):
                async with session.begin():
                    await BudgetService(session).set_budget(1, BudgetPeriod.WEEK, amount)
            with pytest.raises(ValueError):
                async with session.begin():
                    await ExpenseService(session).add_many(
                        1, [ParsedExpense.model_construct(amount=amount)]
                    )
