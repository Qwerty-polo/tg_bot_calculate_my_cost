"""User-related persistence operations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import User


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create(
        self,
        telegram_id: int,
        *,
        username: str | None = None,
        full_name: str | None = None,
    ) -> User:
        """Fetch the user by telegram id, creating the row if necessary."""
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                telegram_id=telegram_id,
                username=username,
                full_name=full_name,
                currency=settings.default_currency,
            )
            self.session.add(user)
            await self.session.flush()
        else:
            # Keep profile fields fresh.
            changed = False
            if username and user.username != username:
                user.username = username
                changed = True
            if full_name and user.full_name != full_name:
                user.full_name = full_name
                changed = True
            if changed:
                await self.session.flush()
        return user
