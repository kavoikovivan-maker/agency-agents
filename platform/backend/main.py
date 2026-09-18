"""Backward-compatible entrypoint: the real application lives in app.main."""
from __future__ import annotations

from .app.main import app

__all__ = ["app"]
