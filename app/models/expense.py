"""Expense model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.enums import ExpenseCategory

if TYPE_CHECKING:
    from app.models.user import User


class Expense(Base, TimestampMixin):
    """A single parsed expense / transaction."""

    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(8), default="UAH")
    occurred_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    merchant: Mapped[str | None] = mapped_column(String(255), default=None)
    category: Mapped[ExpenseCategory] = mapped_column(
        Enum(ExpenseCategory, native_enum=False, length=32),
        default=ExpenseCategory.OTHER,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(String(512), default=None)
    raw_text: Mapped[str | None] = mapped_column(Text, default=None)

    user: Mapped[User] = relationship(back_populates="expenses")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<Expense id={self.id} amount={self.amount} {self.currency} "
            f"category={self.category.value}>"
        )
