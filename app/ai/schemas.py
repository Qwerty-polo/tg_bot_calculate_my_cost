"""Pydantic schemas describing the structured output we expect from the AI."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.config import CURRENCY_CODE
from app.utils.money import validate_amount, validate_currency


class ParsedExpense(BaseModel):
    """A single outgoing transaction extracted from a banking screenshot."""

    amount: float = Field(..., description="Positive amount spent")
    currency: str = Field(default=CURRENCY_CODE)
    occurred_at: datetime | None = Field(
        default=None, description="When the transaction happened"
    )
    merchant: str | None = Field(default=None, max_length=255, description="Store / merchant name")

    @field_validator("amount")
    @classmethod
    def _positive_amount(cls, value: float) -> float:
        return validate_amount(value)

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, value: str) -> str:
        return validate_currency(value)


class ParsedExpenseList(BaseModel):
    """Wrapper so the model returns a JSON object (required by some APIs)."""

    expenses: list[ParsedExpense] = Field(default_factory=list, max_length=100)
