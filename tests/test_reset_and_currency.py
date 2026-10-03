"""Currency validation, historical dates and per-user resets."""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.ai.schemas import ParsedExpense
from app.database.base import Base
from app.models import BudgetPeriod
from app.services import BudgetService, ExpenseService, UserService


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


def test_parsed_expense_rejects_foreign_currency():
    for currency in ("USD", "€", "PLN", "UNKNOWN"):
        with pytest.raises(ValidationError):
            ParsedExpense(amount=10, currency=currency)
    assert ParsedExpense(amount=10, currency="грн").currency == "UAH"
    assert ParsedExpense(amount=10).currency == "UAH"


@pytest.mark.asyncio
async def test_add_many_stores_uah(session):
    user = await UserService(session).get_or_create(1, username="u")
    expenses = ExpenseService(session)
    created = await expenses.add_many(
        user.id, [ParsedExpense(amount=100, currency="UAH", merchant="X")]
    )
    assert created[0].currency == "UAH"


@pytest.mark.asyncio
async def test_add_many_rejects_incoming(session):
    user = await UserService(session).get_or_create(1, username="u")
    expenses = ExpenseService(session)
    created = await expenses.add_many(
        user.id,
        [
            ParsedExpense(amount=230.5, merchant="Silpo"),
            ParsedExpense(amount=5000, merchant="Поповнення картки"),
            ParsedExpense(amount=12, merchant="Cashback"),
        ],
    )
    # Only the real expense is stored; incoming transfers are filtered out.
    assert len(created) == 1
    assert created[0].merchant == "Silpo"


@pytest.mark.asyncio
async def test_add_many_preserves_historical_purchase_date(session):
    from app.utils.timeframe import day_range

    user = await UserService(session).get_or_create(1, username="u")
    expenses = ExpenseService(session)
    old = datetime(2026, 9, 1, 9, 30)
    created = await expenses.add_many(
        user.id, [ParsedExpense(amount=245, merchant="Silpo", occurred_at=old)],
        fallback_dt=datetime(2026, 10, 3, 12, tzinfo=UTC),
    )
    assert created[0].occurred_at == datetime(2026, 9, 1, 6, 30)
    start, end = day_range(datetime(2026, 10, 3, 12, tzinfo=UTC))
    assert await expenses.total_in_range(user.id, start, end) == 0
    start, end = day_range(datetime(2026, 9, 1, 12, tzinfo=UTC))
    assert await expenses.total_in_range(user.id, start, end) == 245


@pytest.mark.asyncio
async def test_add_many_keeps_same_day_purchase_time(session):
    user = await UserService(session).get_or_create(1, username="u")
    expenses = ExpenseService(session)
    today_time = datetime(2026, 1, 15, 9, 15)
    created = await expenses.add_many(
        user.id,
        [ParsedExpense(amount=50, merchant="Cafe", occurred_at=today_time)],
        fallback_dt=datetime(2026, 1, 15, 18, tzinfo=UTC),
    )
    assert created[0].occurred_at == datetime(2026, 1, 15, 7, 15)


@pytest.mark.asyncio
async def test_reset_deletes_only_requesting_user(session):
    users = UserService(session)
    expenses = ExpenseService(session)
    budgets = BudgetService(session)

    alice = await users.get_or_create(1, username="alice")
    bob = await users.get_or_create(2, username="bob")

    await expenses.add_many(alice.id, [ParsedExpense(amount=50, merchant="A")])
    await expenses.add_many(bob.id, [ParsedExpense(amount=70, merchant="B")])
    await budgets.set_budget(alice.id, BudgetPeriod.WEEK, 5000)

    deleted_expenses = await expenses.delete_all_for_user(alice.id)
    deleted_budgets = await budgets.delete_all_for_user(alice.id)

    assert deleted_expenses == 1
    assert deleted_budgets == 1
    # Bob's data is untouched.
    bob_expenses = await expenses.list_in_range(
        bob.id, datetime(2000, 1, 1), datetime(2100, 1, 1)
    )
    assert len(bob_expenses) == 1
