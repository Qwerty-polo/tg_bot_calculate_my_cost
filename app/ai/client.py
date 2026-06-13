"""Thin async wrapper around the Google Gemini chat API.

Gemini is called through the ``openai`` SDK via its OpenAI-compatible endpoint
(``GEMINI_BASE_URL``). The ``openai`` package here is just the HTTP client — the
provider is always Gemini.
"""

from __future__ import annotations

import logging

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    """Return a lazily-created singleton Gemini client."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.gemini_api_key,
            base_url=settings.gemini_base_url,
        )
    return _client


async def chat_json(system_prompt: str, user_prompt: str) -> str:
    """Run a chat completion that is forced to return a JSON object."""
    client = get_client()
    response = await client.chat.completions.create(
        model=settings.gemini_model,
        response_format={"type": "json_object"},
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content or "{}"


async def chat_text(system_prompt: str, user_prompt: str, temperature: float = 0.6) -> str:
    """Run a plain text chat completion."""
    client = get_client()
    response = await client.chat.completions.create(
        model=settings.gemini_model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return (response.choices[0].message.content or "").strip()
