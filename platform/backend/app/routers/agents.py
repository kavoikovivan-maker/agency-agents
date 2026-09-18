from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..catalog import catalog
from ..security import require_session

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("")
def list_agents(
    q: str | None = Query(default=None, description="Free-text search across name/description/division"),
    division: str | None = Query(default=None),
    _: None = Depends(require_session),
) -> dict:
    items = catalog()
    if division:
        items = [a for a in items if a["division"] == division]
    if q:
        needle = q.lower()
        items = [
            a for a in items
            if needle in a["name"].lower() or needle in a["description"].lower() or needle in a["division"].lower()
        ]
    public = [{k: v for k, v in a.items() if k != "keywords"} for a in items]
    return {"count": len(public), "items": public}
