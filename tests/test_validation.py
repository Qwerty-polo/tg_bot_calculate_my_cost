import pytest
from pydantic import ValidationError

from app.ai.analyzer import _heuristic_parse
from app.ai.schemas import ParsedExpense
from app.handlers.budgets import parse_amount
from app.utils.money import validate_amount


@pytest.mark.parametrize("line", [
    "Balance: 9999", "Balance 9999 UAH", "Available 500 UAH", "Залишок 500 грн",
    "Total 500 UAH", "Account 12345678 UAH", "Картка 1234 грн", "UA1234567890123456",
    "12:30 Silpo 230.50 грн", "2026-09-25", "25.09.2026 230.50 UAH",
    "1234567890123456", "1234567890123456 UAH", "Order 12 Cafe 230 UAH",
    "Cafe 100", "Cafe +100 UAH", "Cafe 1e3 UAH", "Cafe 10.123 UAH",
    "Cafe 0 UAH", "Cafe NaN UAH", "Cafe inf UAH", "Cafe 10 USD",
    "Cafe 100 UAH 200 UAH", "Cashback 100 UAH", "Cafe " + "9" * 400 + " UAH",
])
def test_fallback_skips_ambiguous_and_non_transaction_lines(line):
    assert _heuristic_parse(line) == []


@pytest.mark.parametrize("line,amount", [
    ("Silpo 230.50 грн", 230.5), ("Cafe -50 UAH", 50),
    ("Rozetka 1\u00a0850,00 ₴", 1850),
])
def test_fallback_accepts_only_explicit_merchant_amount_lines(line, amount):
    assert [item.amount for item in _heuristic_parse(line)] == [amount]


@pytest.mark.parametrize("amount", [0, -1, float("nan"), float("inf"), -float("inf"),
                                        0.001, 10_000_000_000])
def test_invalid_money_is_rejected(amount):
    with pytest.raises(ValueError):
        validate_amount(amount)
    with pytest.raises(ValidationError):
        ParsedExpense(amount=amount)


@pytest.mark.parametrize("text", ["0", "-1", "NaN", "inf", "1e3", "12:30", "25.09.2026",
                                      "1.234", "100 and 200", "9" * 400, "10000000000"])
def test_invalid_budget_input_is_rejected(text):
    assert parse_amount(text) is None
