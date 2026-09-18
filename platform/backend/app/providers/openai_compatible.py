"""OpenAI-compatible chat completions adapter with bounded retry."""
from __future__ import annotations

import time

import httpx

from ..config import settings
from .base import Provider


class OpenAICompatibleProvider(Provider):
    def __init__(self, api_key: str, base_url: str, model: str, name: str = "openai") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.name = name

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        last_exc: Exception | None = None
        attempts = max(1, settings.provider_max_retries + 1)
        for attempt in range(attempts):
            try:
                response = httpx.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.3,
                    },
                    timeout=settings.provider_timeout_seconds,
                )
                # Configuration/auth/client errors are not transient.
                if 400 <= response.status_code < 500:
                    response.raise_for_status()
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                if attempt >= attempts - 1:
                    break
                time.sleep(min(2 ** attempt, 4))
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if 400 <= exc.response.status_code < 500:
                    raise
                if attempt >= attempts - 1:
                    break
                time.sleep(min(2 ** attempt, 4))
        if last_exc:
            raise RuntimeError(f"Provider temporarily unavailable after {attempts} attempts: {last_exc}") from last_exc
        raise RuntimeError("Provider returned no response")
