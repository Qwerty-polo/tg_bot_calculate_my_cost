"""Application configuration loaded from environment / .env file."""

from __future__ import annotations

from functools import cached_property
from typing import ClassVar

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The bot is UAH-only: every amount is stored and displayed in Ukrainian hryvnia.
CURRENCY_CODE = "UAH"
CURRENCY_SYMBOL = "₴"


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

    # Google's OpenAI-compatible endpoint for the Gemini API. We call Gemini
    # through the ``openai`` SDK by pointing it at this base URL.
    GEMINI_BASE_URL: ClassVar[str] = (
        "https://generativelanguage.googleapis.com/v1beta/openai/"
    )

    # Telegram
    bot_token: str = Field(default="", alias="BOT_TOKEN")

    # Google Gemini (the only supported LLM provider).
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(
        default="gemini-3.5-flash", alias="GEMINI_MODEL"
    )

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/expenses.db",
        alias="DATABASE_URL",
    )

    # OCR
    ocr_engine: str = Field(default="tesseract", alias="OCR_ENGINE")
    ocr_languages: str = Field(default="eng+ukr", alias="OCR_LANGUAGES")
    # Explicit path to the tesseract binary. Leave empty to use the one on
    # PATH (Linux/macOS/CI/Docker). On Windows set e.g.
    # TESSERACT_CMD=C:\\Program Files\\Tesseract-OCR\\tesseract.exe
    tesseract_cmd: str = Field(default="", alias="TESSERACT_CMD")

    # App
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    allowed_user_ids: str = Field(default="", alias="ALLOWED_USER_IDS")

    @field_validator("ocr_engine")
    @classmethod
    def _normalize_engine(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"tesseract", "easyocr"}:
            raise ValueError("OCR_ENGINE must be 'tesseract' or 'easyocr'")
        return value

    @property
    def default_currency(self) -> str:
        """The bot operates exclusively in UAH."""
        return CURRENCY_CODE

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
    def gemini_base_url(self) -> str:
        return self.GEMINI_BASE_URL

    @property
    def has_llm(self) -> bool:
        """Whether a Gemini API key is configured (enables AI features)."""
        return bool(self.gemini_api_key)


settings = Settings()
