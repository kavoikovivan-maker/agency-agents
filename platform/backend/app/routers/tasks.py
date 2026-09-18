from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Artifact, Project, Task
from ..runner import runner
from ..schemas import TaskCreate, TaskOut
from ..security import require_session

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("", response_model=TaskOut)
async def create_task(payload: TaskCreate, db: Session = Depends(get_db), _: None = Depends(require_session)):
    if not db.get(Project, payload.project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    task = Task(
        project_id=payload.project_id,
        conversation_id=payload.conversation_id,
        input_text=payload.input_text,
        status="queued",
    )
    db.add(task)
    db.flush()

    if payload.file_ids:
        artifacts = db.scalars(select(Artifact).where(Artifact.id.in_(payload.file_ids))).all()
        for artifact in artifacts:
            artifact.task_id = task.id

    db.commit()
    db.refresh(task)
    await runner.enqueue(task.id)
    return task


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: str, db: Session = Depends(get_db), _: None = Depends(require_session)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("", response_model=list[TaskOut])
def list_tasks(project_id: str | None = None, db: Session = Depends(get_db), _: None = Depends(require_session)):
    stmt = select(Task).order_by(Task.created_at.desc())
    if project_id:
        stmt = stmt.where(Task.project_id == project_id)
    return db.scalars(stmt).all()


@router.post("/{task_id}/retry", response_model=TaskOut)
async def retry_task(task_id: str, db: Session = Depends(get_db), _: None = Depends(require_session)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status not in {"failed", "cancelled", "interrupted"}:
        raise HTTPException(status_code=400, detail=f"Cannot retry a task in status '{task.status}'")
    task.status = "queued"
    task.cancel_requested = False
    task.error_message = ""
    db.commit()
    db.refresh(task)
    await runner.enqueue(task.id)
    return task


@router.post("/{task_id}/cancel", response_model=TaskOut)
def cancel_task(task_id: str, db: Session = Depends(get_db), _: None = Depends(require_session)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status in {"completed", "failed", "cancelled"}:
        raise HTTPException(status_code=400, detail=f"Cannot cancel a task in status '{task.status}'")
    if task.status == "queued":
        task.status = "cancelled"
    else:
        task.cancel_requested = True
    db.commit()
    db.refresh(task)
    return task
