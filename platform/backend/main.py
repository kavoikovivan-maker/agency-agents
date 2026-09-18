from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "platform" / "web"

DIVISIONS = {
    "academic", "design", "engineering", "finance", "game-development",
    "gis", "healthcare", "marketing", "paid-media", "product",
    "project-management", "research", "sales", "security",
    "spatial-computing", "specialized", "support", "testing",
}

app = FastAPI(title="Company Agency", version="0.1.0")


def parse_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        data = yaml.safe_load(parts[1]) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def catalog() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for division in sorted(DIVISIONS):
        folder = ROOT / division
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.md")):
            meta = parse_frontmatter(path)
            result.append({
                "id": path.stem,
                "division": division,
                "name": meta.get("name") or path.stem,
                "description": meta.get("description") or "",
                "path": str(path.relative_to(ROOT)),
            })
    return result


@app.get("/api/health")
def health() -> dict[str, Any]:
    agents = catalog()
    return {"ok": True, "agents": len(agents), "status": "platform-foundation"}


@app.get("/api/agents")
def agents() -> dict[str, Any]:
    items = catalog()
    return {"count": len(items), "items": items}


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


app.mount("/static", StaticFiles(directory=WEB), name="static")
