"""Application configuration loaded from environment / .env file."""

from __future__ import annotations

from functools import cached_property

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings.

    Values are read from environment variables and an optional ``.env`` file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Telegram
    bot_token: str = Field(default="", alias="BOT_TOKEN")

    # OpenAI
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/expenses.db",
        alias="DATABASE_URL",
    )

    # OCR
    ocr_engine: str = Field(default="tesseract", alias="OCR_ENGINE")
    ocr_languages: str = Field(default="eng+ukr", alias="OCR_LANGUAGES")

    # App
    default_currency: str = Field(default="UAH", alias="DEFAULT_CURRENCY")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    allowed_user_ids: str = Field(default="", alias="ALLOWED_USER_IDS")

    @field_validator("ocr_engine")
    @classmethod
    def _normalize_engine(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"tesseract", "easyocr"}:
            raise ValueError("OCR_ENGINE must be 'tesseract' or 'easyocr'")
        return value

    @cached_property
    def allowed_user_id_set(self) -> set[int]:
        """Parsed set of allowed telegram user ids (empty = allow everyone)."""
        result: set[int] = set()
        for chunk in self.allowed_user_ids.split(","):
            chunk = chunk.strip()
            if chunk:
                result.add(int(chunk))
        return result

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)


settings = Settings()
