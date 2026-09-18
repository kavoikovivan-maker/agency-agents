"""Common provider interface for LLM adapters."""
from __future__ import annotations

from abc import ABC, abstractmethod


class Provider(ABC):
    name: str = "base"
    model: str = ""

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Return the model's text response for the given prompts."""

    def is_mock(self) -> bool:
        return self.name == "mock"
