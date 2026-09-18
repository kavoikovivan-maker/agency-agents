from __future__ import annotations

from pathlib import Path

from app.catalog import catalog, refresh_catalog, DIVISIONS
from app.config import REPO_ROOT


def test_catalog_is_nonempty():
    items = catalog()
    assert len(items) > 0


def test_catalog_count_matches_repository_markdown_files():
    expected = 0
    for division in DIVISIONS:
        folder = REPO_ROOT / division
        if folder.exists():
            expected += len(list(folder.glob("*.md")))
    assert len(catalog()) == expected


def test_catalog_items_have_required_fields():
    for item in catalog():
        assert item["id"]
        assert item["division"] in DIVISIONS
        assert isinstance(item["description"], str)
        assert Path(item["path"]).suffix == ".md"


def test_refresh_catalog_reflects_cache_clear():
    first = catalog()
    refreshed = refresh_catalog()
    assert len(first) == len(refreshed)
