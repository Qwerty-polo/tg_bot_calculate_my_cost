"""Analytics snapshot model.

Stores AI-generated financial analyses so they can be reviewed or compared
over time (e.g. week-over-week spending comparisons).
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class AnalyticsSnapshot(Base, TimestampMixin):
    """A persisted AI financial analysis for a given period."""

    __tablename__ = "analytics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    period: Mapped[str] = mapped_column(String(16))
    # Raw JSON payload of the computed metrics that backed the analysis.
    metrics_json: Mapped[str | None] = mapped_column(Text, default=None)
    # Human-readable AI insight text shown to the user.
    insight_text: Mapped[str | None] = mapped_column(Text, default=None)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AnalyticsSnapshot user_id={self.user_id} period={self.period}>"
