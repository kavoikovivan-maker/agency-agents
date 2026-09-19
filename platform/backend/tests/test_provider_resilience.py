from __future__ import annotations

import httpx

from app.config import settings
from app.providers.openai_compatible import OpenAICompatibleProvider


def _response(status: int, *, headers: dict[str, str] | None = None, content: str = "ok") -> httpx.Response:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    if status == 200:
        return httpx.Response(
            status,
            request=request,
            headers=headers,
            json={"choices": [{"message": {"content": content}}]},
        )
    return httpx.Response(status, request=request, headers=headers)


def test_provider_retries_429_and_respects_retry_after(monkeypatch):
    responses = [
        _response(429, headers={"Retry-After": "2"}),
        _response(200, content="готово"),
    ]
    sleeps: list[float] = []

    monkeypatch.setattr(settings, "provider_max_retries", 3)
    monkeypatch.setattr(settings, "provider_max_retry_wait_seconds", 90)
    monkeypatch.setattr("app.providers.openai_compatible.httpx.post", lambda *a, **k: responses.pop(0))
    monkeypatch.setattr("app.providers.openai_compatible.time.sleep", lambda seconds: sleeps.append(seconds))

    provider = OpenAICompatibleProvider("secret", "https://api.groq.com/openai/v1", "openai/gpt-oss-20b", "groq")
    assert provider.generate("system", "user") == "готово"
    assert sleeps == [2.0]


def test_provider_does_not_retry_auth_error(monkeypatch):
    calls = 0

    def fake_post(*args, **kwargs):
        nonlocal calls
        calls += 1
        return _response(401)

    monkeypatch.setattr(settings, "provider_max_retries", 4)
    monkeypatch.setattr("app.providers.openai_compatible.httpx.post", fake_post)

    provider = OpenAICompatibleProvider("bad", "https://api.groq.com/openai/v1", "openai/gpt-oss-20b", "groq")
    try:
        provider.generate("system", "user")
    except httpx.HTTPStatusError as exc:
        assert exc.response.status_code == 401
    else:
        raise AssertionError("401 must fail immediately")

    assert calls == 1


def test_retry_after_is_bounded(monkeypatch):
    responses = [
        _response(429, headers={"Retry-After": "999"}),
        _response(200, content="ok"),
    ]
    sleeps: list[float] = []

    monkeypatch.setattr(settings, "provider_max_retries", 2)
    monkeypatch.setattr(settings, "provider_max_retry_wait_seconds", 5)
    monkeypatch.setattr("app.providers.openai_compatible.httpx.post", lambda *a, **k: responses.pop(0))
    monkeypatch.setattr("app.providers.openai_compatible.time.sleep", lambda seconds: sleeps.append(seconds))

    provider = OpenAICompatibleProvider("secret", "https://api.groq.com/openai/v1", "openai/gpt-oss-20b", "groq")
    assert provider.generate("system", "user") == "ok"
    assert sleeps == [5.0]
