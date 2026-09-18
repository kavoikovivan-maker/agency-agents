"""Loads the existing markdown agent catalog without mutating source files."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .config import REPO_ROOT

NON_DIVISION_DIRS = {"examples", "integrations", "scripts", "strategy"}
DIVISIONS: list[str] = []


def load_source_divisions() -> list[str]:
    config_path = REPO_ROOT / "divisions.json"
    if not config_path.exists():
        return []
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    divisions = payload.get("divisions", {})
    source = [name for name in divisions if name not in NON_DIVISION_DIRS]
    return sorted(source)


DIVISIONS = load_source_divisions()


def parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not text.startswith("---"):
        return {}, text.strip()
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text.strip()
    try:
        data = yaml.safe_load(parts[1]) or {}
        if not isinstance(data, dict):
            return {}, text.strip()
        return data, (parts[2] or "").strip()
    except Exception:
        return {}, text.strip()


def _build_catalog() -> list[dict[str, Any]]:
    divisions = load_source_divisions()
    result: list[dict[str, Any]] = []
    for division in divisions:
        folder = REPO_ROOT / division
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.md")):
            meta, body = parse_frontmatter(path)
            name = meta.get("name") or path.stem
            description = meta.get("description") or ""
            instructions = body or description
            result.append({
                "id": path.stem,
                "division": division,
                "name": name,
                "description": description,
                "instructions": instructions,
                "path": str(path.relative_to(REPO_ROOT)),
                "keywords": _keywords(division, name, description, instructions),
            })
    return result


@lru_cache(maxsize=1)
def catalog() -> list[dict[str, Any]]:
    return _build_catalog()


def refresh_catalog() -> list[dict[str, Any]]:
    catalog.cache_clear()
    return catalog()


def _keywords(division: str, name: str, description: str, instructions: str) -> set[str]:
    text = f"{division} {name} {description} {instructions}".lower()
    normalized = text.replace("/", " ").replace("-", " ").replace("_", " ")
    tokens = set()
    for raw in normalized.split():
        token = "".join(ch for ch in raw if ch.isalnum())
        if len(token) > 2:
            tokens.add(token)
    return tokens


def find_agent(agent_id: str) -> dict[str, Any] | None:
    for item in catalog():
        if item["id"] == agent_id:
            return item
    return None
