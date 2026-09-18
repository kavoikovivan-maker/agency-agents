from __future__ import annotations

from fastapi import APIRouter, Depends

from ..catalog import catalog
from ..config import settings
from ..providers import get_provider
from ..security import require_session

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health() -> dict:
    return {"ok": True, "agents": len(catalog()), "status": "ready"}


@router.get("/api/settings/runtime")
def runtime_settings(_: None = Depends(require_session)) -> dict:
    provider = get_provider()
    return {
        "provider": provider.name,
        "model": provider.model,
        "configured": settings.provider_configured(),
        "mock_mode": provider.is_mock(),
        "agent_count": len(catalog()),
        "max_agents_per_task": settings.max_agents_per_task,
        "max_upload_mb": settings.max_upload_mb,
    }
