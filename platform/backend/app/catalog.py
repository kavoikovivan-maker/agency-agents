"""Loads the existing markdown agent catalog without mutating source files."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .config import REPO_ROOT

DIVISIONS = {
    "academic", "design", "engineering", "finance", "game-development",
    "gis", "healthcare", "integrations", "marketing", "paid-media", "product",
    "project-management", "research", "sales", "security",
    "spatial-computing", "specialized", "strategy", "support", "testing",
}


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


def _build_catalog() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for division in sorted(DIVISIONS):
        folder = REPO_ROOT / division
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.md")):
            meta = parse_frontmatter(path)
            name = meta.get("name") or path.stem
            description = meta.get("description") or ""
            result.append({
                "id": path.stem,
                "division": division,
                "name": name,
                "description": description,
                "path": str(path.relative_to(REPO_ROOT)),
                "keywords": _keywords(division, name, description),
            })
    return result


@lru_cache(maxsize=1)
def catalog() -> list[dict[str, Any]]:
    return _build_catalog()


def refresh_catalog() -> list[dict[str, Any]]:
    catalog.cache_clear()
    return catalog()


def _keywords(division: str, name: str, description: str) -> set[str]:
    text = f"{division} {name} {description}".lower()
    tokens = set()
    for raw in text.replace("/", " ").replace("-", " ").split():
        token = "".join(ch for ch in raw if ch.isalnum())
        if len(token) > 2:
            tokens.add(token)
    return tokens


def find_agent(agent_id: str) -> dict[str, Any] | None:
    for item in catalog():
        if item["id"] == agent_id:
            return item
    return None
