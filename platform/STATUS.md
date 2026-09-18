# Platform status

## Working
- Agent catalog loader reads all existing markdown agents from the repository
  divisions (read-only, count matches `find <division> -name '*.md'`).
- SQLite persistence for projects, conversations, messages, tasks, task runs,
  artifacts and events (SQLAlchemy models in `app/models.py`).
- Orchestrator: keyword-based classification, 1-6 agent selection from the
  live catalog, concurrent agent execution, a critic/review step, and a final
  synthesis step — all persisted per task.
- Recoverable async task runner: statuses `queued/running/completed/failed/
  cancelled/interrupted`; a process restart marks any task stuck in `running`
  as `interrupted` (recoverable via `/api/tasks/{id}/retry`), and each retry
  increments `attempt`.
- LLM provider layer: deterministic `mock` provider (default, no key needed),
  plus `openai` and `groq` OpenAI-compatible adapters selected via
  `MODEL_PROVIDER` + the relevant API key env var.
- File uploads: extension + size validation, filename sanitization, path
  traversal guard, and best-effort text extraction for txt/md/csv/json/pdf/
  docx/xlsx, attached to task context.
- Web UI: dark graphite SPA — project sidebar, task composer, live task
  progress with status dots, collapsed "agents used" panel, final answer,
  event log, task history, file list, and a settings modal showing the
  active provider/model. Responsive down to 390px.
- REST API covering every endpoint required by `TASK.md`, plus `GET
  /api/tasks` (listing) and `POST /api/auth/login` (optional single-user
  password mode).
- Docker: `docker compose up --build` starts the full app with a persistent
  named volume for `/data` (SQLite db + uploads) and a container healthcheck.
- Automated tests (pytest, mock provider, no network): catalog loading/count,
  SQLite persistence across sessions, orchestrator classification/selection,
  and the full task lifecycle (create → complete → forced failure → retry →
  complete) through the HTTP API. All 15 tests pass.

## Mocked / simplified
- LLM output is the deterministic mock provider unless `OPENAI_API_KEY` or
  `GROQ_API_KEY` is configured — this is intentional per the task spec so the
  whole flow works without a paid key.
- Agent-to-agent handoff is implemented as: agents run concurrently → critic
  reviews all outputs → synthesizer produces the final answer. There is no
  deeper multi-round negotiation between agents (out of scope for the MVP).
- Single-user auth is a lightweight in-memory token issued by `/api/auth/
  login`; there is no multi-user account system (matches the "single-user
  MVP is acceptable" requirement).
- OCR is intentionally not implemented (per instructions); PDF/DOCX/XLSX text
  extraction is text-layer only.

## Known remaining limitations
- The in-memory auth token store in `security.py` is per-process; if
  `APP_PASSWORD` is set, restarting the container invalidates sessions (users
  just log in again — acceptable for local/internal use).
- No pagination on `/api/tasks` or `/api/files` listings; fine at MVP scale.
- No automated browser/UI tests (viewport behavior was checked via CSS media
  queries down to 390px, not with a headless browser).
