"""Async, recoverable task runner with staged handoffs and persistent state."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import delete, select

from .config import settings
from .db import session_scope
from .models import Event, Task, TaskRun
from .orchestrator import (
    build_plan,
    run_critic,
    run_stage,
    run_synthesis,
    select_agents_with_reasons,
)
from .providers import get_provider

logger = logging.getLogger("company_agency.runner")


def _now():
    return datetime.now(timezone.utc)


def _log_event(db, task_id: str, level: str, message: str) -> None:
    db.add(Event(task_id=task_id, level=level, message=message))
    db.commit()


def recover_interrupted_tasks() -> int:
    with session_scope() as db:
        stuck = db.scalars(select(Task).where(Task.status == "running")).all()
        for task in stuck:
            task.status = "interrupted"
            _log_event(db, task.id, "warning", "Процесс был перезапущен во время выполнения. Задача помечена как прерванная и может быть повторена.")
        db.commit()
        return len(stuck)


class TaskRunner:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[str] | None = None
        self._worker_task: asyncio.Task | None = None

    async def start(self) -> None:
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
            except Exception:
                logger.exception("Task %s failed unexpectedly", task_id)
            finally:
                self.queue.task_done()

    def _cancel_requested(self, task_id: str) -> bool:
        with session_scope() as db:
            task = db.get(Task, task_id)
            return bool(task and task.cancel_requested)

    def _mark_cancelled(self, task_id: str) -> None:
        with session_scope() as db:
            task = db.get(Task, task_id)
            if task:
                task.status = "cancelled"
                db.commit()
                _log_event(db, task_id, "warning", "Задача отменена пользователем.")

    async def _process(self, task_id: str) -> None:
        with session_scope() as db:
            task = db.get(Task, task_id)
            if task is None or task.status not in {"queued", "interrupted"}:
                return

            # A retry represents a clean execution attempt. Keep artifacts/events,
            # but remove stale TaskRun rows so the UI never duplicates specialists.
            if task.attempt > 0:
                db.execute(delete(TaskRun).where(TaskRun.task_id == task_id))

            task.status = "running"
            task.attempt += 1
            task.error_message = ""
            task.final_answer = ""
            db.commit()
            _log_event(db, task_id, "info", f"Запуск попытки #{task.attempt}.")

            context_excerpt = "\n\n".join(
                a.extracted_text[:4000] for a in task.artifacts if a.extracted_text
            )
            task_text = task.input_text

        try:
            provider = get_provider()
            agents = select_agents_with_reasons(task_text, settings.max_agents_per_task)
            plan = build_plan(task_text, agents)

            with session_scope() as db:
                task = db.get(Task, task_id)
                task.classification = ",".join(sorted({a["division"] for a in agents}))
                for agent in agents:
                    _log_event(
                        db,
                        task_id,
                        "routing",
                        f"Выбран {agent['id']} | score={agent.get('routing_score', 0)} | "
                        f"mode={agent.get('routing_mode', 'deterministic')} | {agent.get('routing_reason', '')}",
                    )
                _log_event(
                    db,
                    task_id,
                    "plan",
                    "План: " + " -> ".join(
                        f"{stage.index + 1}:{stage.name}[{', '.join(a['id'] for a in stage.agents)}]"
                        for stage in plan
                    ),
                )
                db.commit()

            all_results = []
            upstream_context = context_excerpt
            step_order = 0

            for stage in plan:
                if self._cancel_requested(task_id):
                    self._mark_cancelled(task_id)
                    return

                _stage_context = upstream_context[-12000:] if upstream_context else ""
                with session_scope() as db:
                    for agent in stage.agents:
                        db.add(TaskRun(
                            task_id=task_id,
                            agent_id=agent["id"],
                            division=agent["division"],
                            role="agent",
                            step_order=step_order,
                            status="running",
                            started_at=_now(),
                        ))
                        step_order += 1
                    db.commit()
                    _log_event(db, task_id, "stage", f"Этап {stage.index + 1} «{stage.name}» запущен.")

                stage_results = await run_stage(provider, stage, task_text, _stage_context)

                with session_scope() as db:
                    for result in stage_results:
                        run = db.scalars(
                            select(TaskRun).where(
                                TaskRun.task_id == task_id,
                                TaskRun.agent_id == result.agent_id,
                                TaskRun.status == "running",
                            )
                        ).first()
                        if run:
                            run.status = "completed"
                            run.input_text = result.input_text
                            run.output_text = result.output_text
                            run.finished_at = _now()
                    db.commit()
                    _log_event(db, task_id, "stage", f"Этап {stage.index + 1} «{stage.name}» завершён.")

                all_results.extend(stage_results)
                handoff = "\n\n".join(
                    f"[handoff:{r.agent_id}]\n{r.output_text}" for r in stage_results
                )
                upstream_context = (upstream_context + "\n\n" + handoff).strip()

            if self._cancel_requested(task_id):
                self._mark_cancelled(task_id)
                return

            critic = await run_critic(provider, task_text, all_results)
            with session_scope() as db:
                db.add(TaskRun(
                    task_id=task_id,
                    agent_id=critic.agent_id,
                    division=critic.division,
                    role="critic",
                    step_order=step_order,
                    status="completed",
                    input_text=critic.input_text,
                    output_text=critic.output_text,
                    started_at=_now(),
                    finished_at=_now(),
                ))
                db.commit()
                _log_event(db, task_id, "review", "Критик завершил проверку результатов.")
            step_order += 1

            if self._cancel_requested(task_id):
                self._mark_cancelled(task_id)
                return

            synthesis = await run_synthesis(provider, task_text, all_results, critic)
            with session_scope() as db:
                task = db.get(Task, task_id)
                db.add(TaskRun(
                    task_id=task_id,
                    agent_id=synthesis.agent_id,
                    division=synthesis.division,
                    role="synthesis",
                    step_order=step_order,
                    status="completed",
                    input_text=synthesis.input_text,
                    output_text=synthesis.output_text,
                    started_at=_now(),
                    finished_at=_now(),
                ))
                task.final_answer = synthesis.output_text
                task.status = "completed"
                db.commit()
                _log_event(db, task_id, "info", "Задача полностью завершена.")
        except Exception as exc:
            with session_scope() as db:
                task = db.get(Task, task_id)
                if task:
                    task.status = "failed"
                    task.error_message = f"{type(exc).__name__}: {exc}"
                    db.commit()
                    _log_event(db, task_id, "error", task.error_message)
            raise


runner = TaskRunner()
