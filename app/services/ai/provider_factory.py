"""Configuration-driven construction of the assistant's LLM provider."""

from __future__ import annotations

import logging
from functools import lru_cache

from app.core.config import settings
from app.services.ai.ollama_provider import OllamaProvider
from app.services.ai.provider import LLMProvider

logger = logging.getLogger(__name__)

DISABLED_PROVIDER_NAMES = {"", "none", "disabled"}


def create_provider() -> LLMProvider | None:
    """Build the configured provider, or ``None`` when AI is turned off."""
    provider_name = (settings.ai_provider or "").strip().lower()

    if provider_name in DISABLED_PROVIDER_NAMES:
        return None

    if provider_name == "ollama":
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout_seconds=settings.ollama_timeout_seconds,
            keep_alive=settings.ollama_keep_alive,
            max_attempts=settings.ollama_max_attempts,
            retry_backoff_seconds=settings.ollama_retry_backoff_seconds,
        )

    logger.warning(
        "Unsupported ai_provider %r; using deterministic assistant replies", provider_name
    )
    return None


@lru_cache(maxsize=1)
def _cached_provider() -> LLMProvider | None:
    return create_provider()


def get_llm_provider() -> LLMProvider | None:
    """FastAPI dependency returning the configured provider (or ``None``).

    Returning ``None`` is the supported "assistant disabled" signal; callers
    fall back to the deterministic reply instead of failing the request.
    """
    if not settings.ai_enabled:
        return None
    return _cached_provider()


def reset_provider_cache() -> None:
    """Drop the memoised provider (used by tests and config reloads)."""
    _cached_provider.cache_clear()