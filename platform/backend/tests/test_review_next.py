from __future__ import annotations

from app.catalog import catalog, load_source_divisions
from app.orchestrator import build_agent_prompt, classify


def test_catalog_uses_divisions_json_and_excludes_generated_dirs():
    source_divisions = load_source_divisions()
    assert "engineering" in source_divisions
    assert "integrations" not in source_divisions
    assert "strategy" not in source_divisions
    assert "examples" not in source_divisions
    assert all(item["division"] in source_divisions for item in catalog())


def test_prompt_includes_real_agent_body_and_not_just_frontmatter():
    agent = next(item for item in catalog() if item["id"] == "engineering-backend-architect")
    system, _ = build_agent_prompt(agent, "Design a resilient API", "")
    assert "zero-downtime schema migrations" in system.lower()
    assert "system architecture specification" in system.lower()


def test_russian_routing_uses_multilingual_keywords():
    task = "Рассчитай рецептуру напитка на 1000 литров и проверь себестоимость"
    label = classify(task)
    assert label in {"engineering", "finance", "product", "marketing"}
