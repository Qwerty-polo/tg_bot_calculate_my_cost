from app.ai.analyzer import _heuristic_parse
from app.handlers.budgets import parse_amount
from app.utils.formatting import fmt_money, progress_bar


def test_parse_amount_handles_separators():
    assert parse_amount("5000") == 5000
    assert parse_amount("set to 1 850,50 please") == 1850.5
    assert parse_amount("nope") is None
    assert parse_amount("-100") is None


def test_progress_bar_clamps():
    assert progress_bar(0) == "░" * 10
    assert progress_bar(100) == "█" * 10
    assert progress_bar(150) == "█" * 10


def test_fmt_money_uses_space_separator():
    assert fmt_money(1234567.5, "UAH") == "1 234 567.50 UAH"


def test_heuristic_parse_extracts_amounts():
    text = "Rozetka 1 850,00 грн\nSilpo 230.50 грн\nBalance: 9999"
    expenses = _heuristic_parse(text)
    amounts = sorted(e.amount for e in expenses)
    assert 230.5 in amounts
    assert 1850.0 in amounts
