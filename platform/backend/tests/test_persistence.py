from __future__ import annotations

from app.db import init_db, session_scope
from app.models import Project, Task, TaskRun


def test_project_and_task_persist_across_sessions():
    init_db()
    with session_scope() as db:
        project = Project(name="Persistence Test Project")
        db.add(project)
        db.commit()
        project_id = project.id

    # Simulate a process restart by opening a brand-new session.
    with session_scope() as db:
        loaded = db.get(Project, project_id)
        assert loaded is not None
        assert loaded.name == "Persistence Test Project"

        task = Task(project_id=project_id, input_text="Do something useful", status="queued")
        db.add(task)
        db.commit()
        task_id = task.id

    with session_scope() as db:
        loaded_task = db.get(Task, task_id)
        assert loaded_task is not None
        assert loaded_task.status == "queued"

        run = TaskRun(task_id=task_id, agent_id="engineering-backend-architect", division="engineering", role="agent", step_order=0)
        db.add(run)
        db.commit()

    with session_scope() as db:
        loaded_task = db.get(Task, task_id)
        assert len(loaded_task.runs) == 1
        assert loaded_task.runs[0].agent_id == "engineering-backend-architect"
