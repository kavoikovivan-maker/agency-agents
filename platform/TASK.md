# TASK: finish Company Agency as a production-ready web platform

Work only on branch `company-agency-platform`.
Do NOT rewrite or delete the existing agent catalog. Treat the current Agency Agents repository as the source-of-truth library.

## Goal
Turn the current `platform/` foundation into a complete, runnable internal company AI system accessible from a browser.

## Required result
A user opens the site, creates/selects a project, uploads files, writes a task, and the system:
1. classifies the task;
2. selects the best agents from the existing catalog;
3. runs them through an orchestrator;
4. preserves task state and history;
5. lets agents hand work to one another;
6. returns a consolidated final answer plus artifacts/files;
7. survives restart without losing running/completed tasks.

## Architecture
Keep it pragmatic and self-contained:
- FastAPI backend
- SQLite for MVP persistence
- async job/task runner
- provider abstraction for LLMs
- existing markdown agents loaded dynamically from repository folders
- web UI in `platform/web`
- Docker + docker-compose
- environment variables for secrets only; never hardcode keys

## Must implement

### 1. Agent catalog loader
- Parse all existing agent markdown files.
- Expose divisions, names, descriptions, capabilities.
- Search/filter agents.
- Never modify source agent files at runtime.

### 2. Orchestrator
Create a central orchestrator that:
- receives user task + project context;
- chooses 1-6 relevant agents;
- creates an execution plan;
- runs agents sequentially or in parallel where safe;
- gives later agents relevant outputs from earlier agents;
- includes a critic/reviewer step for important outputs;
- synthesizes one final response.
Do not expose 279 agents as a giant selector by default. Automatic routing is primary.

### 3. LLM provider layer
Support provider adapters with a common interface.
Minimum:
- OpenAI-compatible endpoint
- Groq-compatible endpoint
Configuration from environment variables.
If no provider is configured, app must still boot and clearly show "model not configured".

### 4. Persistence
SQLite tables/models for:
- users (single-user MVP is acceptable)
- projects
- conversations
- messages
- tasks
- task runs
- selected agents
- artifacts
- events/logs
Persist before execution starts so restart recovery is possible.

### 5. Recoverable task runner
- statuses: queued/running/completed/failed/cancelled
- save intermediate step results
- on restart, mark interrupted jobs recoverable and allow retry
- idempotent retries where possible
- human-readable error messages

### 6. Projects + files
Web UI must support:
- create project
- project list
- conversation history
- upload text/PDF/CSV/XLSX/DOCX where feasible
- store files in local data volume for MVP
- extract text safely
- attach files to task context
Avoid OCR unless absolutely necessary.

### 7. Web UI
Polished dark graphite interface, responsive on iPhone and desktop.
Pages/areas:
- Projects/sidebar
- Main chat/task view
- Current task progress
- Agents used (collapsed by default)
- Files
- History
- Settings
Visual style:
- minimal
- deep graphite, low-contrast panels
- no bright gradients
- subtle raised/analog button feel
- status dots for state
- excellent iPhone Safari/PWA behavior
Do not make the interface look like an admin dashboard.

### 8. API
At minimum:
- GET /api/health
- GET /api/agents
- GET/POST /api/projects
- GET/POST /api/projects/{id}/conversations
- POST /api/tasks
- GET /api/tasks/{id}
- POST /api/tasks/{id}/retry
- POST /api/tasks/{id}/cancel
- POST /api/files
- GET /api/settings/runtime

### 9. Security
- no secrets committed
- validate uploads and filenames
- size limits
- basic local auth/session layer or explicit single-user local mode
- safe path handling
- CORS locked down by default

### 10. Docker and operations
`docker compose up --build` must start the full app.
Add:
- persistent volumes for SQLite and uploads
- healthcheck
- .env.example
- startup migration/init
- concise README with exact launch steps

### 11. Quality gates
Before declaring done:
- backend starts cleanly
- health endpoint passes
- agent catalog count is nonzero and matches repository content
- create project works
- create task works
- task persists across restart
- orchestrator selects agents
- mock-provider test path works without paid API
- real provider path is configurable
- upload validation works
- UI works at 390px iPhone width
- no secrets in git
- Docker build succeeds

## Deliverables
Commit all work to `company-agency-platform`.
Add:
- `platform/README.md` with final run instructions
- `platform/.env.example`
- automated tests for catalog, persistence, orchestrator routing, task retry
- a short `platform/STATUS.md` listing what is working, what is mocked, and any remaining blocker

## Important
Do not stop after scaffolding.
Continue until the project can be launched locally with one command and a real task can be submitted through the website.
If an external API key is missing, implement and test the entire flow with a deterministic mock provider, then document exactly which env var enables a real model.
