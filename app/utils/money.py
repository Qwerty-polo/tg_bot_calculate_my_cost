"""Validation shared by parsed transactions and budget input."""

from decimal import Decimal, InvalidOperation


class UnsupportedCurrencyError(ValueError):
    """The input is not explicitly denominated in UAH."""


def validate_currency(value: str | None) -> str:
    if not isinstance(value, str) or value.strip().upper() not in {"UAH", "ГРН", "₴"}:
        raise UnsupportedCurrencyError("Only explicit UAH expenses are supported")
    return "UAH"


def validate_amount(value: float) -> float:
    """Accept finite positive amounts representable by Numeric(12, 2)."""
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Invalid amount") from exc
    if not amount.is_finite() or not Decimal("0") < amount <= Decimal("9999999999.99"):
        raise ValueError("Amount must be finite, positive and within the storage limit")
    if amount != amount.quantize(Decimal("0.01")):
        raise ValueError("Amount must have at most two decimal places")
    return float(amount)
