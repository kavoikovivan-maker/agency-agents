"""Deterministic offline provider used when no real API key is configured."""
from __future__ import annotations

import hashlib
import textwrap

from .base import Provider


class MockProvider(Provider):
    """Produces deterministic, reproducible text without any network access.

    Useful for tests and for running the full orchestration flow without a
    paid API key. Output is a function of the input so retries and tests
    stay stable.
    """

    name = "mock"
    model = "mock-deterministic-v1"

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        digest = hashlib.sha256(f"{system_prompt}\n{user_prompt}".encode()).hexdigest()[:8]
        snippet = textwrap.shorten(user_prompt.strip().replace("\n", " "), width=220, placeholder="…")
        role = textwrap.shorten(system_prompt.strip().replace("\n", " "), width=100, placeholder="…") or "assistant"
        return (
            f"[mock:{digest}] ({role})\n"
            f"Analysed request: {snippet}\n"
            "Deterministic mock output — configure MODEL_PROVIDER + an API key for real model responses."
        )
