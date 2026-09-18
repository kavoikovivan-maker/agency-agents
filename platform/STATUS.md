# Platform status

## Working
- The source agent catalog is loaded from `divisions.json`; generated/non-source
  directories such as `integrations/` and `strategy/` are excluded.
- Every runtime agent uses the real markdown body from its source file as its
  operating instructions, with a prompt-size guard for unusually large files.
- Multilingual routing supports English and Russian, including beverage/company
  tasks (formulation/production, costing, procurement, quality, marketing).
- Selected agents include a persisted human-readable routing reason and score.
- The orchestrator creates a bounded staged plan (technical/business/supporting),
  passes upstream outputs into later stages, then runs critic + final synthesis.
- SQLite persists projects, conversations, tasks, task runs, artifacts and events.
- Retry starts a clean execution attempt without duplicating stale TaskRun rows;
  uploaded artifacts remain attached and are not duplicated.
- Interrupted running tasks are marked recoverable on process restart.
- LLM provider layer supports deterministic `mock`, OpenAI-compatible endpoints,
  and Groq-compatible endpoints.
- Real provider calls have configurable timeout, bounded retry and exponential
  backoff for transient network/server failures; 4xx configuration/auth errors
  are not automatically retried.
- File uploads validate extension/size/path and extract text from txt/md/csv/json,
  PDF, DOCX and XLSX where a text layer exists.
- Web UI shows provider/model truth (including MOCK mode), task progress, routing
  reasons, staged execution plan, agents used, final answer, files and history.
- REST API covers projects, conversations, tasks, retry/cancel, files, runtime
  settings and optional single-user login.
- `docker compose up --build` starts the complete app with persistent storage and
  a healthcheck.
- GitHub Actions validates tests, Docker build/start and `/api/health` on every
  push to `company-agency-platform`.
- Backend suite currently contains 20 tests, including an end-to-end Russian
  beverage task that must select finance plus a relevant technical/product role,
  expose routing/plan/stage events, and return a final answer.

## Runtime modes
- With no API key the whole product runs in deterministic MOCK mode. This is for
  functional verification only and is visibly labelled in the UI.
- For real AI responses set `MODEL_PROVIDER=groq` + `GROQ_API_KEY`, or
  `MODEL_PROVIDER=openai` + `OPENAI_API_KEY`, then restart Docker.

## Known limitations
- Cancellation is cooperative: an in-flight synchronous provider HTTP request is
  allowed to finish, then cancellation is honored before the next stage.
- Authentication is intentionally single-user/local for this version; sessions
  are in-memory and a container restart requires logging in again if
  `APP_PASSWORD` is enabled.
- OCR is intentionally not included; scanned/image-only PDFs need a separate OCR
  pipeline.
- No pagination on task/file listings yet; suitable for current internal/MVP use.
- Browser UI behavior is covered by responsive implementation and CI backend/
  Docker checks, not a full headless-browser end-to-end suite.
