"""Per-user exact-image fingerprints, committed atomically with expenses."""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Upload(Base):
    __tablename__ = "uploads"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
