"""Provider abstraction package."""
from __future__ import annotations

from .base import Provider
from .groq import GroqProvider
from .mock import MockProvider
from .openai_compatible import OpenAICompatibleProvider

__all__ = ["Provider", "MockProvider", "OpenAICompatibleProvider", "GroqProvider", "get_provider"]


def get_provider() -> Provider:
    from ..config import settings

    if settings.model_provider == "openai" and settings.openai_api_key:
        return OpenAICompatibleProvider(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.openai_model,
            name="openai",
        )
    if settings.model_provider == "groq" and settings.groq_api_key:
        return GroqProvider()
    return MockProvider()
