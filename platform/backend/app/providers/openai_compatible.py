"""OpenAI-compatible chat completions adapter with rate-limit aware bounded retry."""
from __future__ import annotations

import email.utils
import time
from datetime import datetime, timezone

import httpx

from ..config import settings
from .base import Provider


def _retry_delay(response: httpx.Response | None, attempt: int) -> float:
    """Return a bounded delay, preferring Retry-After when the provider supplies it."""
    fallback = min(2 ** attempt, 8)
    if response is None:
        return float(fallback)

    value = response.headers.get("retry-after", "").strip()
    if value:
        try:
            return min(max(float(value), 0.0), float(settings.provider_max_retry_wait_seconds))
        except ValueError:
            try:
                retry_at = email.utils.parsedate_to_datetime(value)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                seconds = max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
                return min(seconds, float(settings.provider_max_retry_wait_seconds))
            except (TypeError, ValueError, OverflowError):
                pass

    return float(min(fallback, settings.provider_max_retry_wait_seconds))


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
            response: httpx.Response | None = None
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
                        **({"reasoning_effort": "low", "include_reasoning": False, "max_completion_tokens": 1200}
                           if self.name == "groq" and self.model.startswith("openai/gpt-oss-") else {}),
                    },
                    timeout=settings.provider_timeout_seconds,
                )

                # 429 is transient and must be retried. Other 4xx errors are
                # configuration/auth/request problems and should fail fast.
                if response.status_code == 429:
                    response.raise_for_status()
                if 400 <= response.status_code < 500:
                    response.raise_for_status()

                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                if not isinstance(content, str) or not content.strip():
                    raise RuntimeError("Provider returned an empty completion")
                return content

            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                status = exc.response.status_code
                if 400 <= status < 500 and status != 429:
                    raise

            if attempt >= attempts - 1:
                break
            time.sleep(_retry_delay(response, attempt))

        if last_exc:
            raise RuntimeError(
                f"Provider temporarily unavailable after {attempts} attempts: {last_exc}"
            ) from last_exc
        raise RuntimeError("Provider returned no response")
