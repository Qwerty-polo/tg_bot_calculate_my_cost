from app.ai.analyzer import _heuristic_parse, looks_like_income
from app.handlers.budgets import parse_amount
from app.utils.formatting import fmt_money


def test_parse_amount_handles_separators():
    assert parse_amount("5000") == 5000
    assert parse_amount("set to 1 850,50 please") == 1850.5
    assert parse_amount("nope") is None
    assert parse_amount("-100") is None


def test_fmt_money_prefixes_uah_symbol():
    assert fmt_money(245) == "₴245"
    assert fmt_money(1840) == "₴1 840"
    assert fmt_money(1234567.5) == "₴1 234 567.50"


def test_heuristic_parse_extracts_amounts():
    text = "Rozetka 1 850,00 грн\nSilpo 230.50 грн\nBalance: 9999"
    expenses = _heuristic_parse(text)
    amounts = sorted(e.amount for e in expenses)
    assert 230.5 in amounts
    assert 1850.0 in amounts


def test_heuristic_parse_skips_incoming():
    text = "Silpo 230.50 грн\nПоповнення 5 000,00 грн\nКешбек 12.00 грн"
    expenses = _heuristic_parse(text)
    merchants = [(e.merchant or "").lower() for e in expenses]
    assert any("silpo" in m for m in merchants)
    assert not any("поповнення" in m for m in merchants)
    assert not any("кешбек" in m for m in merchants)


def test_looks_like_income():
    assert looks_like_income("Поповнення картки")
    assert looks_like_income("Переказ від Іван")
    assert looks_like_income("Cashback")
    assert not looks_like_income("Silpo")
    assert not looks_like_income(None)
