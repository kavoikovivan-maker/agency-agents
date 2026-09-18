# REVIEW: required fixes before calling Company Agency ready

I reviewed commit e7b23e4. The platform boots and the plumbing is real, but two core behaviors currently make the "agents" much weaker than the source repository and must be fixed before we treat this as a real agency.

## P0 — Use the actual agent instructions, not only name/description
Current `catalog.py` stores only frontmatter metadata and `orchestrator.build_agent_prompt()` builds a generic system prompt from `name`, `division`, and `description`.

That means the runtime is NOT actually executing the detailed agent playbooks/personas/workflows in the markdown files.

### Required fix
- Parse and retain the markdown body after frontmatter for every source agent.
- Add a field such as `instructions` / `prompt_body` to each catalog entry.
- Build each agent's system prompt from the real markdown agent content.
- Preserve a short wrapper with task/context boundaries, but do not discard the source instructions.
- Add tests proving a unique phrase from a source agent file appears in the prompt passed to the provider.

## P0 — Catalog must honor divisions.json exactly
Current `DIVISIONS` incorrectly includes `integrations` and `strategy`.
The repository's own `divisions.json` explicitly says:
- `integrations/` contains generated conversion outputs and is NOT a source division.
- `strategy/` contains playbooks/runbooks and has no agent frontmatter and is NOT a source division.

### Required fix
- Load source division names from `divisions.json` instead of duplicating a hard-coded set.
- Exclude non-division directories exactly as repository rules define.
- Test catalog count against the actual division list from `divisions.json`.
- Ensure generated integration files are never treated as independent agents.

## P1 — Routing must work for Russian and normal natural-language tasks
Current classification/selection is mostly English keyword overlap. A Russian task such as:
"Рассчитай рецептуру напитка на 1000 литров и проверь себестоимость"
will likely fall through to arbitrary fallback agents.

### Required fix
Implement multilingual routing:
- normalize Cyrillic/Latin text;
- use provider-assisted routing when a real provider is configured;
- keep a deterministic offline fallback using a bilingual synonym/domain map;
- routing output should explain selected agents and confidence/reason;
- add Russian routing tests for engineering, finance, marketing, production-style/business tasks.

## P1 — Execution plan should support real handoffs
Current flow is parallel agents -> critic -> synthesis. Keep that as the fast path, but add an optional sequential dependency plan:
- planner emits stages/dependencies;
- outputs from upstream agents are passed to dependent downstream agents;
- persist the plan and each handoff in TaskRun/Event;
- cap loops/rounds to prevent runaway execution.

## P1 — Verify cancellation/restart behavior under active provider calls
Add tests for:
- cancel requested while agents are running;
- process restart after TaskRun rows exist but before synthesis;
- retry does not duplicate stale TaskRuns or artifacts;
- provider timeout surfaces a clean error and remains retryable.

## P2 — Runtime truth in UI
The UI should clearly display:
- provider (mock/OpenAI/Groq)
- whether answers are mock or real
- selected agents and why
- task execution stage
Do not let mock mode look like a real AI result.

## Acceptance gate
Do not report "ready" until:
1. source markdown bodies are actually injected into agent prompts;
2. catalog follows divisions.json and excludes integrations/strategy;
3. Russian task routing tests pass;
4. tests pass;
5. Docker build + health pass;
6. submit one Russian sample task through the website and show selected agents + final output.

Commit all fixes to `company-agency-platform` and update `platform/STATUS.md` with exact remaining limitations.
