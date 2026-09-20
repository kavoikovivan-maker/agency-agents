"""Task classification, agent selection, staged execution and synthesis."""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any

from .catalog import catalog
from .config import settings
from .providers.base import Provider

MAX_AGENT_INSTRUCTIONS_CHARS = 3000

CLASSES = {
    "engineering": ["code", "bug", "api", "backend", "frontend", "database", "deploy", "infrastructure", "test", "архитект", "код", "база", "дебаг", "сервис", "производ", "технолог"],
    "design": ["design", "ui", "ux", "visual", "brand", "persona", "дизайн", "интерфейс"],
    "marketing": ["marketing", "campaign", "ads", "seo", "content", "growth", "маркет", "реклама", "бренд"],
    "sales": ["sales", "lead", "deal", "pipeline", "outreach", "продаж", "лид", "сделк"],
    "finance": ["finance", "budget", "forecast", "invoice", "revenue", "cost", "costing", "финанс", "бюджет", "себестоимост", "стоимост", "доход"],
    "product": ["product", "roadmap", "feature", "spec", "requirement", "formula", "formulation", "продукт", "рецептур", "специфик", "требован"],
    "research": ["research", "analysis", "study", "survey", "исслед", "анализ", "опрос"],
    "support": ["support", "ticket", "customer", "helpdesk", "поддержк", "клиент"],
    "security": ["security", "vulnerability", "audit", "compliance", "безопасност", "аудит", "комплаенс", "качество"],
    "general": [],
}

DOMAIN_DIVISION_BOOSTS = {
    "beverage": {"product": 5, "engineering": 5, "specialized": 4, "research": 2},
    "finance": {"finance": 7, "product": 2},
    "procurement": {"finance": 4, "project-management": 3, "specialized": 3, "sales": 1},
    "quality": {"specialized": 5, "research": 4, "engineering": 3, "product": 2},
    "marketing": {"marketing": 6, "sales": 3, "product": 2},
}

DOMAIN_TERMS = {
    "beverage": ["напит", "лимонад", "молоч", "рецептур", "брикс", "brix", "сахар", "сырье", "производ", "технолог"],
    "finance": ["себестоим", "стоимост", "бюджет", "маржа", "цена", "cost", "costing", "finance"],
    "procurement": ["закуп", "поставщик", "сырье", "упаков", "склад", "supply", "procurement"],
    "quality": ["качество", "риск", "безопасност", "контроль", "стандарт", "compliance", "quality"],
    "marketing": ["маркет", "продаж", "рынок", "бренд", "реклама", "marketing", "sales"],
}


# Distinctive phrases route all catalog divisions, not just the original
# software/marketing subset. These hints supplement, not replace, agent
# identity scoring and the beverage safety filter.
DIVISION_HINTS = {
    "academic": ("академическ", "диссертац", "научную статью", "academic"),
    "design": ("дизайн", "интерфейс", "ux", "ui макет", "design"),
    "engineering": ("backend", "frontend", "api", "программир", "исходный код"),
    "finance": ("финансов", "себестоимост", "бюджет", "маржа", "finance"),
    "game-development": ("разработк игр", "игровой движок", "unity", "unreal", "game development"),
    "gis": ("геоинформац", "геоданных", "картограф", "gis", "геопространств"),
    "healthcare": ("медицин", "пациент", "клиник", "healthcare"),
    "marketing": ("маркетинг", "маркетингов", "продвижени", "marketing"),
    "paid-media": ("рекламный кабинет", "контекстная реклама", "медиабаинг",
                   "таргетированная реклама", "paid media"),
    "product": ("дорожную карту продукта", "продуктов", "product roadmap", "управление продуктом"),
    "project-management": ("управление проектом", "план проекта", "project management"),
    "research": ("исследован", "научный обзор", "опрос", "research"),
    "sales": ("продаж", "коммерческое предложение", "sales"),
    "security": ("кибербезопас", "уязвимост", "информационная безопасность", "security audit"),
    "spatial-computing": ("дополненн", "виртуальн",
                          "spatial computing", "visionos", "ar vr"),
    "specialized": ("цепочку поставок", "закуп", "поставщик", "supply chain"),
    "support": ("поддержка клиент", "служба поддержки", "обращения клиент", "helpdesk"),
    "testing": ("тестировани", "автотест", "регрессионный тест", "quality assurance"),
}


def _normalize_text(text: str) -> str:
    lowered = text.lower().replace("ё", "е")
    lowered = re.sub(r"[^a-zа-я0-9\s.%-]", " ", lowered)
    return " ".join(lowered.split())


def classify(task_text: str) -> str:
    lowered = _normalize_text(task_text)
    best_label, best_score = "general", 0
    for label, words in CLASSES.items():
        score = sum(1 for w in words if w in lowered)
        if score > best_score:
            best_label, best_score = label, score
    return best_label


def detect_domains(task_text: str) -> set[str]:
    normalized = _normalize_text(task_text)
    found: set[str] = set()
    for domain, terms in DOMAIN_TERMS.items():
        if any(term in normalized for term in terms):
            found.add(domain)
    return found


def _task_tokens(task_text: str) -> set[str]:
    return {
        tok for tok in _normalize_text(task_text).split()
        if len(tok) > 2 and any(ch.isalpha() for ch in tok)
    }

# Domain expertise cannot be inferred from a generic division alone. The source
# catalog currently contains software engineers, not beverage technologists.
BEVERAGE_PRIMARY_IDS = ("operations-manager", "product-manager")
BEVERAGE_RELATED_IDS = {
    "operations-manager", "product-manager", "supply-chain-strategist",
    "specialized-pricing-analyst", "product-trend-researcher",
}
SOFTWARE_TERMS = (
    "api", "backend", "frontend", "software", "программ", "приложен",
    "сайт", "код", "docker", "wordpress", "базу данных",
)


def _score_agent(agent: dict[str, Any], task_tokens: set[str], domains: set[str]) -> int:
    # Only the specialist identity/description may provide a strong semantic
    # match. Long unrelated agent instructions contain many incidental terms.
    identity = _normalize_text(
        f"{agent['id']} {agent['name']} {agent['description']}"
    )
    identity_tokens = set(identity.replace("-", " ").split())
    score = 3 * len(identity_tokens & task_tokens)
    score += min(2, len(agent["keywords"] & task_tokens))
    for domain in domains:
        if domain == "beverage":
            if agent["id"] in BEVERAGE_PRIMARY_IDS:
                score += 10
            elif agent["id"] in BEVERAGE_RELATED_IDS:
                score += 4
            # Do not reward every engineer for a beverage recipe.
            continue
        score += DOMAIN_DIVISION_BOOSTS.get(domain, {}).get(agent["division"], 0)
    return score


def select_agents_with_reasons(task_text: str, max_agents: int = 6) -> list[dict[str, Any]]:
    tokens = _task_tokens(task_text)
    domains = detect_domains(task_text)
    software_task = any(term in _normalize_text(task_text) for term in SOFTWARE_TERMS)
    beverage_task = "beverage" in domains and not software_task
    candidates = catalog()
    if beverage_task:
        # A software/WordPress engineer must not be forced into recipe,
        # manufacturing or beverage marketing work by a division-wide bonus.
        candidates = [a for a in candidates if a["division"] != "engineering"]

    scored: list[tuple[int, dict[str, Any]]] = [
        (_score_agent(agent, tokens, domains), agent) for agent in candidates
    ]
    scored.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()

    def add(score: int, agent: dict[str, Any], reason: str) -> None:
        if len(selected) < max(1, max_agents) and agent["id"] not in selected_ids:
            selected.append({
                **agent,
                "routing_score": score,
                "routing_reason": reason,
                "routing_mode": "deterministic",
            })
            selected_ids.add(agent["id"])

    required_ids: list[str] = []
    # Prioritize clear domain-specific department names before generic scores.
    normalized_task = _normalize_text(task_text)
    required_divisions: list[str] = [
        division for division, hints in DIVISION_HINTS.items()
        if any(hint in normalized_task for hint in hints)
        and (not beverage_task or division != "engineering")
    ]
    if beverage_task:
        required_ids.extend(BEVERAGE_PRIMARY_IDS)
    elif "beverage" in domains:
        required_divisions.extend(["product", "engineering"])
    if "finance" in domains:
        required_divisions.append("finance")
    if "procurement" in domains:
        required_ids.append("supply-chain-strategist")
        required_divisions.append("finance")
    if "quality" in domains:
        required_ids.append("operations-manager")
        required_divisions.append("research")
    if "marketing" in domains:
        required_divisions.append("marketing")

    for agent_id in dict.fromkeys(required_ids):
        matches = [(score, a) for score, a in scored if a["id"] == agent_id]
        if matches:
            score, agent = matches[0]
            add(score, agent, f"Профильная роль {agent_id} для: {', '.join(sorted(domains))}")

    for division in dict.fromkeys(required_divisions):
        matches = [(score, a) for score, a in scored
                   if a["division"] == division and a["id"] not in selected_ids]
        if matches:
            score, agent = matches[0]
            add(score, agent, f"Нужна роль из направления {division} для: {', '.join(sorted(domains))}")

    for score, agent in scored:
        if len(selected) >= max(1, max_agents):
            break
        if score <= 0 or agent["id"] in selected_ids:
            continue
        overlap = sorted(agent["keywords"] & tokens)
        reason = ("совпали термины: " + ", ".join(overlap[:5])) if overlap else (
            "профильная роль для: " + ", ".join(sorted(domains))
        )
        add(score, agent, reason)

    if not selected:
        fallback_ids = ("product-manager", "business-strategist", "research-synthesist")
        for agent_id in fallback_ids:
            matches = [(score, a) for score, a in scored if a["id"] == agent_id]
            if matches:
                add(*matches[0], "резервная универсальная роль")
            if len(selected) >= min(3, max(1, max_agents)):
                break
    if not selected and scored:
        score, agent = scored[0]
        add(score, agent, "резервная роль")
    return selected[:max(1, max_agents)]


def select_agents(task_text: str, max_agents: int = 6) -> list[dict[str, Any]]:
    return select_agents_with_reasons(task_text, max_agents)


@dataclass
class StepResult:
    agent_id: str
    division: str
    role: str
    input_text: str
    output_text: str


@dataclass
class PlanStage:
    index: int
    name: str
    agents: list[dict[str, Any]]


def build_plan(task_text: str, agents: list[dict[str, Any]]) -> list[PlanStage]:
    technical = [a for a in agents if a["division"] in {"product", "engineering", "specialized", "research"}]
    business = [a for a in agents if a["division"] in {"finance", "project-management", "marketing", "sales", "security"}]
    stages: list[PlanStage] = []
    used: set[str] = set()
    if technical:
        stages.append(PlanStage(0, "technical", technical[:3]))
        used |= {a["id"] for a in technical[:3]}
    remaining_business = [a for a in business if a["id"] not in used]
    if remaining_business:
        stages.append(PlanStage(len(stages), "business-risk", remaining_business[:3]))
        used |= {a["id"] for a in remaining_business[:3]}
    leftovers = [a for a in agents if a["id"] not in used]
    if leftovers:
        stages.append(PlanStage(len(stages), "supporting", leftovers[:2]))
    return stages[:3] or [PlanStage(0, "analysis", agents[:3])]


def _trim_instructions(text: str) -> tuple[str, bool]:
    if len(text) <= MAX_AGENT_INSTRUCTIONS_CHARS:
        return text, False
    head = text[:1900]
    tail = text[-800:]
    return head + "\n\n[...source instructions trimmed...]\n\n" + tail, True


def build_agent_prompt(agent: dict[str, Any], task_text: str, context_excerpt: str) -> tuple[str, str]:
    source_instructions = (agent.get("instructions") or agent.get("description") or "").strip()
    source_instructions, trimmed = _trim_instructions(source_instructions)
    trim_note = "\nSource brief was safely trimmed for prompt size." if trimmed else ""
    system = (
        f"You are the '{agent['name']}' agent from the {agent['division']} division. "
        "Use the source agent brief below as your primary operating instructions.\n"
        f"Source brief:\n{source_instructions or 'General domain expertise.'}{trim_note}\n\n"
        "Stay within the source persona. Produce concrete, checkable work. "
        "When the user writes in Russian, answer in Russian unless asked otherwise. "
        "Keep the response concise (up to 500 words), avoid repetition and do not invent missing inputs."
    )
    user = task_text if not context_excerpt else f"{task_text}\n\nUpstream/project context:\n{context_excerpt[-2200:]}"
    return system, user


async def run_agents_concurrently(
    provider: Provider,
    agents: list[dict[str, Any]],
    task_text: str,
    context_excerpt: str,
) -> list[StepResult]:
    semaphore = asyncio.Semaphore(settings.provider_max_concurrency)

    async def run_one(agent: dict[str, Any]) -> StepResult:
        system, user = build_agent_prompt(agent, task_text, context_excerpt)
        async with semaphore:
            output = await asyncio.to_thread(provider.generate, system, user)
        return StepResult(agent_id=agent["id"], division=agent["division"], role="agent", input_text=user, output_text=output)

    return list(await asyncio.gather(*(run_one(a) for a in agents)))


async def run_stage(
    provider: Provider,
    stage: PlanStage,
    task_text: str,
    context_excerpt: str,
) -> list[StepResult]:
    return await run_agents_concurrently(provider, stage.agents, task_text, context_excerpt)


async def run_critic(provider: Provider, task_text: str, results: list[StepResult]) -> StepResult:
    combined = "\n\n".join(f"[{r.agent_id}]\n{r.output_text[:1250]}" for r in results)
    system = (
        "You are a critical reviewer. Check the outputs for gaps, contradictions, unsafe assumptions, "
        "math/unit mistakes, and missed requirements. Be brief and specific. Reply in the user's language."
    )
    user = f"Original task:\n{task_text}\n\nAgent outputs:\n{combined}"
    output = await asyncio.to_thread(provider.generate, system, user)
    return StepResult(agent_id="critic-reviewer", division="orchestrator", role="critic", input_text=user, output_text=output)


async def run_synthesis(provider: Provider, task_text: str, results: list[StepResult], critic: StepResult) -> StepResult:
    combined = "\n\n".join(f"[{r.agent_id}]\n{r.output_text[:1250]}" for r in results)
    system = (
        "You are the final orchestrator. Combine the specialist outputs and critic review into one "
        "clear final answer. Preserve calculations, assumptions, risks and actionable next steps. "
        "Reply in the user's language."
    )
    user = f"Original task:\n{task_text}\n\nAgent outputs:\n{combined}\n\nCritic review:\n{critic.output_text}"
    output = await asyncio.to_thread(provider.generate, system, user)
    return StepResult(agent_id="synthesizer", division="orchestrator", role="synthesis", input_text=user, output_text=output)
