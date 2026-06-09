"""Alembic migration environment.

Runs migrations synchronously by deriving a sync SQLAlchemy URL from the
application's (possibly async) ``DATABASE_URL``.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

# Import models so their tables are registered on Base.metadata.
import app.models  # noqa: F401
from alembic import context
from app.config import settings
from app.database.base import Base
from app.database.session import _ensure_sqlite_dir

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _sync_url() -> str:
    """Convert an async DB URL into a sync one for Alembic."""
    _ensure_sqlite_dir(settings.database_url)
    url = settings.database_url
    return url.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg2")


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _sync_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
