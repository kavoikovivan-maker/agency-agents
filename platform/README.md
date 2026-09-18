# Company Agency Platform

Standalone web platform built on top of the Agency Agents catalog.

## Goal
Turn the existing agent library into a company-internal AI workspace with:
- web chat and projects
- agent orchestration
- persistent task history
- file-aware workflows
- model/provider configuration
- logs and recoverable task execution

## Safety
The original agent catalog on `main` remains untouched. Platform work lives on the `company-agency-platform` branch.

## Local start
```bash
cd platform
docker compose up --build
```

Open http://localhost:8080

## Current foundation
- FastAPI backend
- catalog API reading the existing agent folders
- health endpoint
- lightweight web shell
- Docker packaging

Next: orchestration runtime, persistence, model adapters, project/file workspace, authentication.
