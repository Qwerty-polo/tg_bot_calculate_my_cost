"""Chart generation with matplotlib (headless Agg backend).

Each function returns PNG bytes, ready to be wrapped in an aiogram
``BufferedInputFile``. Generation runs in a worker thread to avoid blocking
the event loop.
"""

from __future__ import annotations

import asyncio
import io
from collections.abc import Mapping, Sequence

import matplotlib

matplotlib.use("Agg")  # noqa: E402 - must be set before pyplot import

import matplotlib.pyplot as plt  # noqa: E402

_COLORS = [
    "#4C72B0",
    "#DD8452",
    "#55A868",
    "#C44E52",
    "#8172B3",
    "#937860",
    "#DA8BC3",
    "#8C8C8C",
    "#CCB974",
]


def _fig_to_png(fig) -> bytes:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    buffer.seek(0)
    return buffer.read()


def _category_pie_sync(categories: Sequence[Mapping]) -> bytes:
    labels = [c["name"] for c in categories]
    sizes = [c["amount"] for c in categories]
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.pie(
        sizes,
        labels=labels,
        autopct="%1.0f%%",
        startangle=90,
        colors=_COLORS[: len(sizes)],
        wedgeprops={"edgecolor": "white", "linewidth": 1.5},
    )
    ax.set_title("Spending by category", fontsize=14, fontweight="bold")
    ax.axis("equal")
    return _fig_to_png(fig)


def _bar_sync(daily_totals: Mapping[str, float], title: str) -> bytes:
    days = list(daily_totals.keys())
    values = list(daily_totals.values())
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(days, values, color="#4C72B0")
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_ylabel("Spent")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.autofmt_xdate(rotation=45)
    return _fig_to_png(fig)


def _line_sync(daily_totals: Mapping[str, float], title: str) -> bytes:
    days = list(daily_totals.keys())
    values = list(daily_totals.values())
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(days, values, marker="o", color="#C44E52", linewidth=2)
    ax.fill_between(range(len(values)), values, alpha=0.15, color="#C44E52")
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_ylabel("Spent")
    ax.grid(True, linestyle="--", alpha=0.4)
    fig.autofmt_xdate(rotation=45)
    return _fig_to_png(fig)


async def category_pie_chart(categories: Sequence[Mapping]) -> bytes | None:
    """Pie chart of spending per category. ``None`` if there is no data."""
    if not categories:
        return None
    return await asyncio.to_thread(_category_pie_sync, categories)


async def weekly_spending_chart(daily_totals: Mapping[str, float]) -> bytes | None:
    """Bar chart of daily spending across the week."""
    if not daily_totals:
        return None
    return await asyncio.to_thread(_bar_sync, daily_totals, "Weekly spending")


async def monthly_trend_chart(daily_totals: Mapping[str, float]) -> bytes | None:
    """Line chart of daily spending across the month."""
    if not daily_totals:
        return None
    return await asyncio.to_thread(_line_sync, daily_totals, "Monthly spending trend")
