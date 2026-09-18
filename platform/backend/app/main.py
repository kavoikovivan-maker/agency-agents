"""FastAPI application entrypoint for the Company Agency platform."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import REPO_ROOT, settings
from .db import init_db
from .routers import agents, auth, files, health, projects, tasks
from .runner import recover_interrupted_tasks, runner

WEB = REPO_ROOT / "platform" / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    init_db()
    recover_interrupted_tasks()
    await runner.start()
    yield
    await runner.stop()


app = FastAPI(title="Company Agency", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(agents.router)
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(files.router)


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


if WEB.exists():
    app.mount("/static", StaticFiles(directory=WEB), name="static")
