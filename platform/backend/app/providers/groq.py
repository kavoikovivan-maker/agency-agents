"""Groq-compatible adapter — shares the OpenAI chat completions wire format."""
from __future__ import annotations

from ..config import settings
from .openai_compatible import OpenAICompatibleProvider


class GroqProvider(OpenAICompatibleProvider):
    def __init__(self) -> None:
        super().__init__(
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
            model=settings.groq_model,
            name="groq",
        )
