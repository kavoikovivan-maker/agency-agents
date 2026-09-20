"""Comprehensive offline catalog, department routing and multi-stage handoff checks.

The mock model exercises every agent without consuming Groq requests. A
separate real-AI smoke workflow verifies one live multi-agent task.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict

from app.catalog import catalog, load_source_divisions
from app.orchestrator import (
    PlanStage, build_agent_prompt, build_plan, run_critic, run_stage,
    run_synthesis, select_agents_with_reasons,
)
from app.providers.mock import MockProvider


TASKS_BY_DIVISION = {
    "academic": "Подготовь академическую научную статью по методологии исследования",
    "design": "Сделай дизайн интерфейса мобильного приложения",
    "engineering": "Спроектируй backend API программного сервиса",
    "finance": "Составь финансовый бюджет компании",
    "game-development": "Опиши разработку игры на движке Unity",
    "gis": "Проанализируй геоинформационные данные для картографии",
    "healthcare": "Опиши медицинский процесс для клиники без диагноза",
    "marketing": "Подготовь маркетинговый план продвижения",
    "paid-media": "Настрой рекламный кабинет для контекстной рекламы",
    "product": "Разработай продуктовую дорожную карту",
    "project-management": "Составь план проекта и управление проектом",
    "research": "Проведи исследование потребителей и опрос",
    "sales": "Подготовь план продаж и коммерческое предложение",
    "security": "Проверь кибербезопасность и уязвимости приложения",
    "spatial-computing": "Спроектируй опыт дополненной реальности для очков",
    "specialized": "Оптимизируй цепочку поставок сырья",
    "support": "Организуй службу поддержки клиентов",
    "testing": "Разработай автотесты и регрессионное тестирование",
}


def test_each_real_department_gets_its_own_task():
    divisions = set(load_source_divisions())
    assert divisions == set(TASKS_BY_DIVISION), (divisions - TASKS_BY_DIVISION.keys(), TASKS_BY_DIVISION.keys() - divisions)
    for division, task in TASKS_BY_DIVISION.items():
        agents = select_agents_with_reasons(task, max_agents=4)
        ids = [a["id"] for a in agents]
        assert division in {a["division"] for a in agents}, (division, ids)
        assert len(ids) == len(set(ids)), division
        stages = build_plan(task, agents)
        assert sorted(ids) == sorted(a["id"] for stage in stages for a in stage.agents), division


def test_all_catalog_agents_can_answer_with_real_instructions_offline():
    provider = MockProvider()
    entries = catalog()
    assert len(entries) >= 264
    assert {a["division"] for a in entries} == set(TASKS_BY_DIVISION)
    ids = set()
    for agent in entries:
        assert agent["id"] not in ids, f"Duplicate ID: {agent['id']}"
        ids.add(agent["id"])
        assert agent["instructions"].strip(), agent["id"]
        system, user = build_agent_prompt(agent, "Тест работы специалиста", "")
        assert agent["name"] in system, agent["id"]
        assert "Source brief:" in system, agent["id"]
        output = provider.generate(system, user)
        assert output.startswith("[mock:"), agent["id"]


def test_each_department_passes_context_to_next_agent_and_synthesis():
    grouped = defaultdict(list)
    for agent in catalog():
        grouped[agent["division"]].append(agent)
    provider = MockProvider()

    async def verify(division, agents):
        first = await run_stage(provider, PlanStage(0, "first", [agents[0]]),
                                "Проверка передачи между специалистами", "")
        handoff = f"[handoff:{first[0].agent_id}]\\n{first[0].output_text[:900]}"
        second = await run_stage(provider, PlanStage(1, "second", [agents[-1]]),
                                 "Проверка передачи между специалистами", handoff)
        assert first[0].agent_id in second[0].input_text, division
        critic = await run_critic(provider, "Проверь результат", first + second)
        final = await run_synthesis(provider, "Сведи результат", first + second, critic)
        assert critic.output_text.startswith("[mock:"), division
        assert final.output_text.startswith("[mock:"), division
        assert division == first[0].division == second[0].division

    async def all_departments():
        for division, agents in grouped.items():
            assert agents, division
            await verify(division, agents)

    asyncio.run(all_departments())
    assert set(grouped) == set(TASKS_BY_DIVISION)
