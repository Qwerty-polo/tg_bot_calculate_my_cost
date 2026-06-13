"""Pydantic schemas describing the structured output we expect from the AI."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.config import CURRENCY_CODE


class ParsedExpense(BaseModel):
    """A single outgoing transaction extracted from a banking screenshot."""

    amount: float = Field(..., description="Positive amount spent")
    currency: str = Field(default=CURRENCY_CODE)
    occurred_at: datetime | None = Field(
        default=None, description="When the transaction happened"
    )
    merchant: str | None = Field(default=None, description="Store / merchant name")

    @field_validator("amount")
    @classmethod
    def _positive_amount(cls, value: float) -> float:
        return abs(value)

    @field_validator("currency")
    @classmethod
    def _force_uah(cls, _value: str) -> str:
        # The bot is UAH-only: ignore whatever currency the screenshot/AI
        # reports and always store hryvnia.
        return CURRENCY_CODE


class ParsedExpenseList(BaseModel):
    """Wrapper so the model returns a JSON object (required by some APIs)."""

    expenses: list[ParsedExpense] = Field(default_factory=list)
