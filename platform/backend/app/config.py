"""Runtime configuration loaded from environment variables."""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    val = os.environ.get(name)
    if val is None or not val.strip():
        return default
    try:
        return int(val)
    except ValueError:
        return default


class Settings:
    """Central place for all environment-driven configuration."""

    def __init__(self) -> None:
        self.data_dir = Path(os.environ.get("APP_DATA_DIR", str(REPO_ROOT / "platform" / "backend" / "data")))
        self.uploads_dir = self.data_dir / "uploads"
        self.db_path = self.data_dir / "app.db"

        self.max_upload_mb = _env_int("MAX_UPLOAD_MB", 20)
        self.max_agents_per_task = _env_int("MAX_AGENTS_PER_TASK", 6)

        self.app_password = os.environ.get("APP_PASSWORD", "").strip()
        allowed = os.environ.get("ALLOWED_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080")
        self.allowed_origins = [o.strip() for o in allowed.split(",") if o.strip()]

        self.model_provider = os.environ.get("MODEL_PROVIDER", "mock").strip().lower()

        self.openai_api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        self.openai_base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
        self.openai_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip()

        self.groq_api_key = os.environ.get("GROQ_API_KEY", "").strip()
        self.groq_base_url = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip()
        self.groq_model = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant").strip()

        self.worker_poll_seconds = _env_int("WORKER_POLL_SECONDS", 1) or 1

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)

    def provider_configured(self) -> bool:
        if self.model_provider == "openai":
            return bool(self.openai_api_key)
        if self.model_provider == "groq":
            return bool(self.groq_api_key)
        return False

    def effective_provider_name(self) -> str:
        """Return the provider that will actually be used (falls back to mock)."""
        if self.provider_configured():
            return self.model_provider
        return "mock"


settings = Settings()
