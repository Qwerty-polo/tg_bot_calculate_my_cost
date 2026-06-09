"""Async database engine and session management."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings
from app.database.base import Base

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _ensure_sqlite_dir(database_url: str) -> None:
    """Create the parent directory for a SQLite database file if needed."""
    marker = ":///"
    if "sqlite" in database_url and marker in database_url:
        path = database_url.split(marker, 1)[1]
        # Strip a leading "./" and ignore in-memory databases.
        if path and path != ":memory:":
            directory = os.path.dirname(path)
            if directory:
                os.makedirs(directory, exist_ok=True)


def get_engine() -> AsyncEngine:
    """Return a lazily-created singleton async engine."""
    global _engine
    if _engine is None:
        _ensure_sqlite_dir(settings.database_url)
        _engine = create_async_engine(settings.database_url, future=True)
    return _engine


def create_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return a lazily-created singleton session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _session_factory


async def init_models() -> None:
    """Create tables for development / first run (Alembic handles migrations)."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Provide a transactional scope around a series of operations."""
    factory = create_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
