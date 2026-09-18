"""Filename/path safety helpers and a minimal single-user session layer."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time
from pathlib import Path

from fastapi import HTTPException, Request, status

from .config import settings

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_active_tokens: dict[str, float] = {}
_TOKEN_TTL_SECONDS = 60 * 60 * 12


def sanitize_filename(filename: str) -> str:
    """Strip any path components and unsafe characters from an uploaded filename."""
    name = Path(filename).name
    name = _SAFE_CHARS.sub("_", name).strip("._")
    return name or "file"


def safe_join(base: Path, *parts: str) -> Path:
    """Join path parts under base, raising if the result escapes base (path traversal guard)."""
    candidate = base.joinpath(*parts).resolve()
    base_resolved = base.resolve()
    if base_resolved not in candidate.parents and candidate != base_resolved:
        raise HTTPException(status_code=400, detail="Invalid path")
    return candidate


def issue_token() -> str:
    token = secrets.token_urlsafe(32)
    _active_tokens[token] = time.time() + _TOKEN_TTL_SECONDS
    return token


def _token_valid(token: str) -> bool:
    expiry = _active_tokens.get(token)
    if expiry is None:
        return False
    if expiry < time.time():
        _active_tokens.pop(token, None)
        return False
    return True


def check_password(candidate: str) -> bool:
    if not settings.app_password:
        return False
    return hmac.compare_digest(
        hashlib.sha256(candidate.encode()).hexdigest(),
        hashlib.sha256(settings.app_password.encode()).hexdigest(),
    )


def require_session(request: Request) -> None:
    """FastAPI dependency enforcing the optional single-user session.

    When APP_PASSWORD is not configured the app runs in explicit single-user
    local mode and every request is allowed.
    """
    if not settings.app_password:
        return
    token = request.headers.get("x-app-token") or request.cookies.get("app_token")
    if not token or not _token_valid(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
