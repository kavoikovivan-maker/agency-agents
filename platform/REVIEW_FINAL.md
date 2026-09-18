# FINAL REVIEW PASS — make Company Agency operationally trustworthy

This is the next required pass after commit ae5c1e2. Work only on branch `company-agency-platform`.

## 1. Fix Russian/business routing so it selects appropriate agents, not just a broad class
The current Russian test only asserts that classification lands in one of several labels. That is too weak.

Required:
- Add a deterministic bilingual domain map for beverage/company tasks:
  - recipe/formulation/technology/production
  - costing/finance
  - procurement/supply
  - quality/compliance
  - marketing/sales
- For a task like:
  "Рассчитай рецептуру молочного лимонада на 1000 литров, Брикс 4.8-4.9, проверь себестоимость и риски производства"
  the selected agent set must include finance/costing plus at least one operations/engineering/product/specialized role that is plausibly relevant.
- Add tests that assert selected agent IDs/divisions, not just a classification label.
- Avoid arbitrary fallback agents when meaningful Russian domain terms are present.

## 2. Add explicit routing reasons
Persist and expose for every selected agent:
- score/confidence
- short human-readable reason
- whether selected by deterministic routing or provider-assisted routing
Show this in the UI under a collapsed "Почему выбраны эти агенты" section.

## 3. Implement staged handoffs (minimal but real)
Current parallel -> critic -> synthesis is acceptable as a fast path, but add a real staged mode:
- planner produces 2-4 stages
- stage N receives outputs from relevant prior stages
- later agents get upstream outputs in context
- persist plan and handoffs
- hard cap total stages and total agent calls
- prevent loops

For the beverage sample task, expected rough plan:
A. formulation/technical analysis
B. costing / procurement / production-risk analysis
C. critic/reviewer
D. synthesis

## 4. Make task cancellation and retry reliable
Add integration tests for:
- cancel while provider call is in-flight
- restart after TaskRun rows exist but before synthesis
- retry after provider timeout
- retry must not duplicate stale TaskRun rows
- retry must not duplicate uploaded artifacts
Return clear status/events in UI.

## 5. Provider timeout and resilience
- configurable request timeout
- map provider timeout/network errors to retryable task errors
- exponential backoff with a small max retry count
- never retry auth/4xx configuration errors automatically

## 6. Agent prompt size guard
Now that full markdown bodies are injected, enforce a prompt-size guard:
- preserve the most important source instructions
- trim safely if an agent file is too large
- log when trimming occurs
- add a test for this behavior

## 7. End-to-end proof
Before reporting ready:
- all tests pass
- Docker build + health pass
- submit one Russian beverage task through API or UI
- show selected agents, routing reasons, staged plan, and final mock output
- then repeat with real provider only if API key is configured; do not require a key for acceptance
- update `platform/STATUS.md` with exact remaining limitations

Commit and push everything to `company-agency-platform`.
