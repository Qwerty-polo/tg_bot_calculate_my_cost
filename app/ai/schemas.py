"""Pydantic schemas describing the structured output we expect from the AI."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import ExpenseCategory


class ParsedExpense(BaseModel):
    """A single transaction extracted from a banking screenshot."""

    amount: float = Field(..., description="Positive amount spent")
    currency: str = Field(default="UAH")
    occurred_at: datetime | None = Field(
        default=None, description="When the transaction happened"
    )
    merchant: str | None = Field(default=None, description="Store / merchant name")
    category: ExpenseCategory = Field(default=ExpenseCategory.OTHER)
    description: str | None = Field(default=None, description="Short description")

    @field_validator("amount")
    @classmethod
    def _positive_amount(cls, value: float) -> float:
        return abs(value)

    @field_validator("currency")
    @classmethod
    def _normalize_currency(cls, value: str) -> str:
        value = (value or "UAH").strip().upper()
        # Normalize common symbols / spellings.
        mapping = {"₴": "UAH", "ГРН": "UAH", "$": "USD", "€": "EUR", "£": "GBP"}
        return mapping.get(value, value)

    @field_validator("category", mode="before")
    @classmethod
    def _coerce_category(cls, value: object) -> ExpenseCategory:
        if isinstance(value, ExpenseCategory):
            return value
        return ExpenseCategory.from_value(str(value) if value is not None else None)


class ParsedExpenseList(BaseModel):
    """Wrapper so the model returns a JSON object (required by some APIs)."""

    expenses: list[ParsedExpense] = Field(default_factory=list)
