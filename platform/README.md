# Company Agency Platform

Standalone web platform built on top of the Agency Agents catalog. Turns the
existing agent library into an internal AI workspace: projects, file-aware
tasks, an orchestrator that routes work across the existing markdown agents,
a critic/review step, a consolidated final answer, and a recoverable task
runner backed by SQLite.

## Safety
The original agent catalog on `main` remains untouched. Platform work lives on
the `company-agency-platform` branch. Agent markdown files are only read, never
modified at runtime.

## Local start

```bash
cd platform
docker compose up --build
```

Open http://localhost:8080

The app boots and is fully usable with **no API key** — a deterministic mock
LLM provider powers the whole flow (task classification, agent execution,
critic review, final synthesis) so you can exercise every feature for free.

To use a real model, copy `.env.example` to `.env` in `platform/` and set:

```bash
MODEL_PROVIDER=openai   # or groq
OPENAI_API_KEY=sk-...
```

then re-run `docker compose up --build`.

## What it does
1. You create/select a project, optionally attach a file, and describe a task.
2. The orchestrator classifies the task and selects 1-6 relevant agents from
   the existing markdown catalog based on keyword relevance.
3. Selected agents run concurrently through the configured LLM provider.
4. A critic/reviewer step checks the combined outputs for gaps.
5. A synthesis step produces one consolidated final answer.
6. Every step, status, and log line is persisted to SQLite so a container
   restart never loses a running or completed task — interrupted tasks are
   marked recoverable and can be retried from the UI or API.

## Architecture
- **Backend**: FastAPI (`platform/backend/app`)
  - `catalog.py` — loads/parses the existing markdown agents (read-only)
  - `models.py` / `db.py` — SQLAlchemy models + SQLite persistence
  - `providers/` — pluggable LLM adapters: `mock`, `openai`, `groq`
  - `orchestrator.py` — classification, agent selection, agent/critic/synthesis prompting
  - `runner.py` — async recoverable task runner (queued/running/completed/failed/cancelled/interrupted)
  - `files.py` — upload validation + text extraction (txt/md/csv/json/pdf/docx/xlsx)
  - `security.py` — filename/path sanitization, optional single-user session
  - `routers/` — REST API
- **Frontend**: static vanilla JS/CSS in `platform/web` (no build step), dark
  graphite theme, responsive down to 390px (iPhone width).
- **Docker**: `platform/Dockerfile` + `platform/docker-compose.yml` with a
  persistent named volume for the SQLite DB and uploads, and a healthcheck.

## API
```
GET  /api/health
GET  /api/agents
GET  /api/projects
POST /api/projects
GET  /api/projects/{id}/conversations
POST /api/projects/{id}/conversations
GET  /api/tasks?project_id=...
POST /api/tasks
GET  /api/tasks/{id}
POST /api/tasks/{id}/retry
POST /api/tasks/{id}/cancel
POST /api/files
GET  /api/files?project_id=...
GET  /api/settings/runtime
POST /api/auth/login          (only relevant when APP_PASSWORD is set)
```

## Tests
```bash
cd platform/backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
```

Covers: agent catalog loading/counts, SQLite persistence across sessions,
orchestrator classification/agent selection, and the full task lifecycle
(create → run → complete → forced-failure → retry → complete) through the
HTTP API using the mock provider.

## Security notes
- No secrets are committed; all keys come from environment variables
  (see `.env.example`).
- Uploads are validated by extension and size (`MAX_UPLOAD_MB`), filenames are
  sanitized, and stored paths are checked against path traversal.
- CORS is locked to `ALLOWED_ORIGINS` (defaults to localhost only).
- Optional single-user password mode via `APP_PASSWORD`; if unset the app runs
  in explicit single-user local mode with no login required.

See `platform/STATUS.md` for what is fully working vs. mocked.
