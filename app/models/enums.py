"""Enumerations shared across models and services."""

from __future__ import annotations

import enum


class BudgetPeriod(str, enum.Enum):
    """Budget planning periods."""

    WEEK = "week"
    MONTH = "month"
