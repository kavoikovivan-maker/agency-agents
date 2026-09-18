"""Task classification, agent selection, execution plan and synthesis."""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any

from .catalog import catalog
from .providers.base import Provider

CLASSES = {
    "engineering": ["code", "bug", "api", "backend", "frontend", "database", "deploy", "infrastructure", "test", "архитект", "код", "api", "база", "дебаг", "сервис"],
    "design": ["design", "ui", "ux", "visual", "brand", "persona", "дизайн", "интерфейс", "ux", "ui"],
    "marketing": ["marketing", "campaign", "ads", "seo", "content", "growth", "маркет", "кампейн", "seo", "контент", "реклама"],
    "sales": ["sales", "lead", "deal", "pipeline", "outreach", "продаж", "лид", "сделк", "воркфлоу"],
    "finance": ["finance", "budget", "forecast", "invoice", "revenue", "финанс", "бюджет", "себестоимост", "стоимост", "доход"],
    "product": ["product", "roadmap", "feature", "spec", "requirement", "продукт", "фича", "roadmap", "специфик", "требован"],
    "research": ["research", "analysis", "study", "survey", "исслед", "анализ", "опрос", "деталь"],
    "support": ["support", "ticket", "customer", "helpdesk", "поддержк", "тикет", "клиент"],
    "security": ["security", "vulnerability", "audit", "compliance", "безопасност", "аудит", "комплаенс"],
    "general": [],
}


def _normalize_text(text: str) -> str:
    lowered = text.lower()
    lowered = lowered.replace("ё", "е")
    lowered = re.sub(r"[^a-zа-я0-9\s]", " ", lowered)
    return " ".join(lowered.split())


def classify(task_text: str) -> str:
    lowered = _normalize_text(task_text)
    best_label, best_score = "general", 0
    for label, words in CLASSES.items():
        score = sum(1 for w in words if w in lowered)
        if score > best_score:
            best_label, best_score = label, score
    return best_label


def _score_agent(agent: dict[str, Any], task_tokens: set[str]) -> int:
    return len(agent["keywords"] & task_tokens)


def select_agents(task_text: str, max_agents: int = 6) -> list[dict[str, Any]]:
    normalized = _normalize_text(task_text)
    tokens = {tok for tok in normalized.split() if len(tok) > 2}
    scored = [(_score_agent(a, tokens), a) for a in catalog()]
    scored.sort(key=lambda pair: pair[0], reverse=True)

    selected = [a for score, a in scored if score > 0][:max_agents]
    if not selected:
        fallback_ids = {"engineering-backend-architect", "product-feedback-synthesizer", "design-ux-researcher"}
        selected = [a for a in catalog() if a["id"] in fallback_ids][: max(1, min(3, max_agents))]
    if not selected:
        selected = catalog()[: max(1, min(3, max_agents))]
    return selected[: max(1, max_agents)]


@dataclass
class StepResult:
    agent_id: str
    division: str
    role: str
    input_text: str
    output_text: str


def build_agent_prompt(agent: dict[str, Any], task_text: str, context_excerpt: str) -> tuple[str, str]:
    source_instructions = (agent.get("instructions") or agent.get("description") or "").strip()
    system = (
        f"You are the '{agent['name']}' agent from the {agent['division']} division. "
        "Use the source agent brief below as your primary operating instructions. "
        f"Source brief:\n{source_instructions or 'General domain expertise.'}\n\n"
        "Stay within the source persona and respond concisely with concrete, actionable output for the task."
    )
    user = task_text if not context_excerpt else f"{task_text}\n\nAttached context:\n{context_excerpt}"
    return system, user


async def run_agents_concurrently(
    provider: Provider,
    agents: list[dict[str, Any]],
    task_text: str,
    context_excerpt: str,
) -> list[StepResult]:
    async def run_one(agent: dict[str, Any]) -> StepResult:
        system, user = build_agent_prompt(agent, task_text, context_excerpt)
        output = await asyncio.to_thread(provider.generate, system, user)
        return StepResult(agent_id=agent["id"], division=agent["division"], role="agent", input_text=user, output_text=output)

    return list(await asyncio.gather(*(run_one(a) for a in agents)))


async def run_critic(provider: Provider, task_text: str, results: list[StepResult]) -> StepResult:
    combined = "\n\n".join(f"[{r.agent_id}]\n{r.output_text}" for r in results)
    system = (
        "You are a critical reviewer. Check the agent outputs below for gaps, contradictions, "
        "or missed requirements relative to the original task. Be brief and specific."
    )
    user = f"Original task:\n{task_text}\n\nAgent outputs:\n{combined}"
    output = await asyncio.to_thread(provider.generate, system, user)
    return StepResult(agent_id="critic-reviewer", division="orchestrator", role="critic", input_text=user, output_text=output)


async def run_synthesis(provider: Provider, task_text: str, results: list[StepResult], critic: StepResult) -> StepResult:
    combined = "\n\n".join(f"[{r.agent_id}]\n{r.output_text}" for r in results)
    system = (
        "You are the orchestrator's final synthesizer. Combine the agent outputs and the critic's "
        "review into one consolidated, well-structured final answer for the user."
    )
    user = (
        f"Original task:\n{task_text}\n\nAgent outputs:\n{combined}\n\n"
        f"Critic review:\n{critic.output_text}"
    )
    output = await asyncio.to_thread(provider.generate, system, user)
    return StepResult(agent_id="synthesizer", division="orchestrator", role="synthesis", input_text=user, output_text=output)
