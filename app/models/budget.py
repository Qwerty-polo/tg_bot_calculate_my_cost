"""Budget model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.enums import BudgetPeriod

if TYPE_CHECKING:
    from app.models.user import User


class Budget(Base, TimestampMixin):
    """A weekly or monthly budget for a user."""

    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("user_id", "period", name="uq_budget_user_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    period: Mapped[BudgetPeriod] = mapped_column(
        Enum(BudgetPeriod, native_enum=False, length=16)
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(8), default="UAH")

    user: Mapped[User] = relationship(back_populates="budgets")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Budget user_id={self.user_id} {self.period.value}={self.amount}>"
