"""Enumerations shared across models and services."""

from __future__ import annotations

import enum


class ExpenseCategory(str, enum.Enum):
    """Canonical expense categories used for automatic categorization."""

    FOOD = "food"
    TRANSPORT = "transport"
    SHOPPING = "shopping"
    ENTERTAINMENT = "entertainment"
    SUBSCRIPTIONS = "subscriptions"
    CAFES = "cafes"
    HEALTH = "health"
    UTILITIES = "utilities"
    OTHER = "other"

    @classmethod
    def from_value(cls, value: str | None) -> ExpenseCategory:
        """Best-effort coercion of an arbitrary string into a category."""
        if not value:
            return cls.OTHER
        normalized = value.strip().lower()
        for member in cls:
            if member.value == normalized:
                return member
        return cls.OTHER

    @property
    def emoji(self) -> str:
        return _CATEGORY_EMOJI.get(self, "💸")

    @property
    def title(self) -> str:
        return self.value.capitalize()


_CATEGORY_EMOJI: dict[ExpenseCategory, str] = {
    ExpenseCategory.FOOD: "🍞",
    ExpenseCategory.TRANSPORT: "🚌",
    ExpenseCategory.SHOPPING: "🛍️",
    ExpenseCategory.ENTERTAINMENT: "🎬",
    ExpenseCategory.SUBSCRIPTIONS: "🔁",
    ExpenseCategory.CAFES: "☕",
    ExpenseCategory.HEALTH: "💊",
    ExpenseCategory.UTILITIES: "💡",
    ExpenseCategory.OTHER: "💸",
}


class BudgetPeriod(str, enum.Enum):
    """Budget planning periods."""

    WEEK = "week"
    MONTH = "month"
