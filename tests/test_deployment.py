"""Build-context policy and the upload migration's compatibility with existing data."""

from datetime import datetime
from fnmatch import fnmatchcase
from pathlib import Path

import sqlalchemy as sa

from alembic import command
from alembic.config import Config
from app.config import settings
from app.models import Expense, User

ROOT = Path(__file__).resolve().parents[1]


def included_in_context(path):
    """Evaluate the literal/glob subset used by this project's ignore policy."""
    included = True
    parents = [path, *[str(p) for p in Path(path).parents if str(p) != "."]]
    parents = [p.replace("\\", "/") for p in parents]
    for line in (ROOT / ".dockerignore").read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        negative = line.startswith("!")
        pattern = line.removeprefix("!")
        patterns = [pattern, pattern.removeprefix("**/")]
        if any(fnmatchcase(p, pat) for p in parents for pat in patterns):
            included = negative
    return included


def test_build_context_excludes_secrets_and_local_artifacts():
    for path in (
        ".env", ".env.production", "secrets.env", ".git/config", ".idea/workspace.xml",
        ".vscode/settings.json", "data/expenses.db", "expenses.db-wal", "local.sqlite3",
        ".venv/Scripts/python.exe", ".python/python.exe", ".uv-cache/archive/file",
        "app/__pycache__/main.pyc", ".pytest_cache/state", ".ruff_cache/state",
        "debug.log", "tmp/screenshot.jpg", "screenshot.png",
        "nested/.env", "nested/.env.production", "nested/secrets.env",
        "nested/.git/config", "nested/.idea/workspace.xml", "nested/.pytest_cache/state",
    ):
        assert not included_in_context(path), path
    for path in (
        "app/main.py", "app/ocr/ocr_service.py", "requirements.txt", "alembic.ini",
        "alembic/versions/c2d3e4f5a6b7_upload_fingerprints.py", "README.md", ".env.example",
        "tests/test_bot_reliability.py", "scripts/smoke_test.py", "docs/demo/example.png",
    ):
        assert included_in_context(path), path


def test_upload_migration_preserves_existing_records(tmp_path, monkeypatch):
    database = tmp_path / "migrations.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{database}")
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "b1c2d3e4f5a6")
    engine = sa.create_engine(f"sqlite:///{database}")
    try:
        with engine.begin() as connection:
            legacy_users = sa.Table("users", sa.MetaData(), autoload_with=connection)
            connection.execute(legacy_users.insert().values(id=1, telegram_id=1, currency="UAH"))
            connection.execute(Expense.__table__.insert().values(
                user_id=1, amount=50, occurred_at=datetime(2026, 1, 1), merchant="Cafe"
            ))
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert "uploads" in sa.inspect(connection).get_table_names()
            assert connection.scalar(sa.select(User.timezone)) == "Europe/Kyiv"
            assert connection.scalar(sa.select(Expense.occurred_at)) == datetime(2026, 1, 1)
            assert connection.scalar(sa.select(sa.func.count()).select_from(Expense)) == 1
        command.downgrade(config, "b1c2d3e4f5a6")
        with engine.connect() as connection:
            assert "uploads" not in sa.inspect(connection).get_table_names()
            assert connection.scalar(sa.select(sa.func.count()).select_from(Expense)) == 1
    finally:
        engine.dispose()


def test_pillow_pin_contains_confirmed_security_fix():
    assert "Pillow==12.1.1" in (ROOT / "requirements.txt").read_text(encoding="utf-8")
