from __future__ import annotations

from app.catalog import catalog, load_source_divisions
from app.orchestrator import (
    MAX_AGENT_INSTRUCTIONS_CHARS,
    _trim_instructions,
    build_agent_prompt,
    build_plan,
    classify,
    select_agents_with_reasons,
)


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


def test_beverage_task_selects_technical_and_finance_roles_with_reasons():
    task = (
        "Рассчитай рецептуру молочного лимонада на 1000 литров, "
        "Брикс 4.8-4.9, проверь себестоимость и риски производства"
    )
    agents = select_agents_with_reasons(task, max_agents=6)
    divisions = {a["division"] for a in agents}
    assert "finance" in divisions
    assert divisions.intersection({"engineering", "product", "specialized"})
    assert all(a.get("routing_reason") for a in agents)
    assert all(a.get("routing_mode") for a in agents)
    assert "study-abroad-advisor" not in {a["id"] for a in agents}
    assert "security-threat-intelligence-analyst" not in {a["id"] for a in agents}

    plan = build_plan(task, agents)
    assert 1 <= len(plan) <= 3
    assert any(stage.name == "technical" for stage in plan)
    assert any(stage.name == "business-risk" for stage in plan)


def test_agent_prompt_size_guard_preserves_head_and_tail():
    source = "HEAD-IMPORTANT\n" + ("x" * (MAX_AGENT_INSTRUCTIONS_CHARS + 5000)) + "\nTAIL-IMPORTANT"
    trimmed, was_trimmed = _trim_instructions(source)
    assert was_trimmed is True
    assert len(trimmed) < len(source)
    assert "HEAD-IMPORTANT" in trimmed
    assert "TAIL-IMPORTANT" in trimmed
    assert "trimmed" in trimmed
