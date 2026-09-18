from __future__ import annotations

import asyncio

from app.orchestrator import classify, run_agents_concurrently, select_agents
from app.providers.mock import MockProvider


def test_classify_picks_engineering_for_code_task():
    assert classify("There is a bug in the backend API deployment") == "engineering"


def test_classify_falls_back_to_general():
    assert classify("...") == "general"


def test_select_agents_bounded_between_one_and_max():
    agents = select_agents("Design a new onboarding experience for our mobile UI", max_agents=6)
    assert 1 <= len(agents) <= 6
    assert all("id" in a and "division" in a for a in agents)


def test_select_agents_relevant_to_keywords():
    agents = select_agents("We need help with SEO and marketing campaign content", max_agents=6)
    divisions = {a["division"] for a in agents}
    assert "marketing" in divisions


def test_run_agents_concurrently_uses_mock_provider():
    provider = MockProvider()
    agents = select_agents("Write a database migration script", max_agents=2)

    async def go():
        return await run_agents_concurrently(provider, agents, "Write a database migration script", "")

    results = asyncio.run(go())
    assert len(results) == len(agents)
    for result in results:
        assert result.output_text.startswith("[mock:")
