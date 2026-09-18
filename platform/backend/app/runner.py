"""Async, recoverable task runner. Tasks survive process restart via SQLite state."""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from .catalog import find_agent
from .config import settings
from .db import session_scope
from .models import Artifact, Event, Task, TaskRun
from .orchestrator import run_agents_concurrently, run_critic, run_synthesis, select_agents
from .providers import get_provider

logger = logging.getLogger("company_agency.runner")

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


def _log_event(db, task_id: str, level: str, message: str) -> None:
    db.add(Event(task_id=task_id, level=level, message=message))
    db.commit()


def recover_interrupted_tasks() -> int:
    """Mark tasks left in 'running' by a previous process as recoverable. Called at startup."""
    with session_scope() as db:
        stuck = db.scalars(select(Task).where(Task.status == "running")).all()
        for task in stuck:
            task.status = "interrupted"
            _log_event(db, task.id, "warning", "Process restarted while task was running; marked interrupted and recoverable via retry.")
        db.commit()
        return len(stuck)


class TaskRunner:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[str] | None = None
        self._worker_task: asyncio.Task | None = None

    async def start(self) -> None:
        # Recreate the queue bound to whichever event loop is running now —
        # important because the app can be started/stopped multiple times
        # within one process (e.g. under test).
        self.queue = asyncio.Queue()
        self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        if self._worker_task:
            self._worker_task.cancel()

    async def enqueue(self, task_id: str) -> None:
        if self.queue is None:
            raise RuntimeError("TaskRunner not started")
        await self.queue.put(task_id)

    async def _worker_loop(self) -> None:
        while True:
            task_id = await self.queue.get()
            try:
                await self._process(task_id)
            except Exception:  # noqa: BLE001 - keep the worker alive across failures
                logger.exception("Task %s failed unexpectedly", task_id)
            finally:
                self.queue.task_done()

    async def _process(self, task_id: str) -> None:
        with session_scope() as db:
            task = db.get(Task, task_id)
            if task is None:
                return
            if task.status not in {"queued", "interrupted"}:
                return
            task.status = "running"
            task.attempt += 1
            task.error_message = ""
            db.commit()
            _log_event(db, task_id, "info", f"Run attempt #{task.attempt} started.")
            context_excerpt = "\n\n".join(
                a.extracted_text[:4000] for a in task.artifacts if a.extracted_text
            )
            task_text = task.input_text

        try:
            provider = get_provider()
            agents = select_agents(task_text, settings.max_agents_per_task)

            with session_scope() as db:
                task = db.get(Task, task_id)
                if task.cancel_requested:
                    task.status = "cancelled"
                    db.commit()
                    return
                task.classification = ",".join(sorted({a["division"] for a in agents}))
                for i, agent in enumerate(agents):
                    db.add(TaskRun(
                        task_id=task_id, agent_id=agent["id"], division=agent["division"],
                        role="agent", step_order=i, status="running",
                    ))
                db.commit()

            results = await run_agents_concurrently(provider, agents, task_text, context_excerpt)

            with session_scope() as db:
                task = db.get(Task, task_id)
                for i, result in enumerate(results):
                    run = db.scalars(
                        select(TaskRun).where(TaskRun.task_id == task_id, TaskRun.agent_id == result.agent_id)
                    ).first()
                    if run:
                        run.status = "completed"
                        run.input_text = result.input_text
                        run.output_text = result.output_text
                if task.cancel_requested:
                    task.status = "cancelled"
                    db.commit()
                    return
                db.commit()

            critic = await run_critic(provider, task_text, results)
            with session_scope() as db:
                db.add(TaskRun(
                    task_id=task_id, agent_id=critic.agent_id, division=critic.division,
                    role="critic", step_order=len(results), status="completed",
                    input_text=critic.input_text, output_text=critic.output_text,
                ))
                db.commit()

            synthesis = await run_synthesis(provider, task_text, results, critic)
            with session_scope() as db:
                task = db.get(Task, task_id)
                db.add(TaskRun(
                    task_id=task_id, agent_id=synthesis.agent_id, division=synthesis.division,
                    role="synthesis", step_order=len(results) + 1, status="completed",
                    input_text=synthesis.input_text, output_text=synthesis.output_text,
                ))
                task.final_answer = synthesis.output_text
                task.status = "completed"
                db.commit()
                _log_event(db, task_id, "info", "Task completed.")
        except Exception as exc:  # noqa: BLE001
            with session_scope() as db:
                task = db.get(Task, task_id)
                if task:
                    task.status = "failed"
                    task.error_message = f"{type(exc).__name__}: {exc}"
                    db.commit()
                    _log_event(db, task_id, "error", task.error_message)
            raise


runner = TaskRunner()
