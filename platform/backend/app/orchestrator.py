"""Task classification, agent selection, execution plan and synthesis."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from .catalog import catalog
from .providers.base import Provider

CLASSES = {
    "engineering": ["code", "bug", "api", "backend", "frontend", "database", "deploy", "infrastructure", "test"],
    "design": ["design", "ui", "ux", "visual", "brand", "persona"],
    "marketing": ["marketing", "campaign", "ads", "seo", "content", "growth"],
    "sales": ["sales", "lead", "deal", "pipeline", "outreach"],
    "finance": ["finance", "budget", "forecast", "invoice", "revenue"],
    "product": ["product", "roadmap", "feature", "spec", "requirement"],
    "research": ["research", "analysis", "study", "survey"],
    "support": ["support", "ticket", "customer", "helpdesk"],
    "security": ["security", "vulnerability", "audit", "compliance"],
    "general": [],
}


def classify(task_text: str) -> str:
    lowered = task_text.lower()
    best_label, best_score = "general", 0
    for label, words in CLASSES.items():
        score = sum(1 for w in words if w in lowered)
        if score > best_score:
            best_label, best_score = label, score
    return best_label


def _score_agent(agent: dict[str, Any], task_tokens: set[str]) -> int:
    return len(agent["keywords"] & task_tokens)


def select_agents(task_text: str, max_agents: int = 6) -> list[dict[str, Any]]:
    tokens = {tok for tok in task_text.lower().replace("-", " ").split() if len(tok) > 2}
    scored = [(_score_agent(a, tokens), a) for a in catalog()]
    scored.sort(key=lambda pair: pair[0], reverse=True)

    selected = [a for score, a in scored if score > 0][:max_agents]
    if not selected:
        # deterministic fallback: a small generalist set so the flow always produces output
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
    system = (
        f"You are the '{agent['name']}' agent from the {agent['division']} division. "
        f"Focus: {agent['description'] or 'general expertise for this division'}. "
        "Respond concisely with concrete, actionable output for the given task."
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
