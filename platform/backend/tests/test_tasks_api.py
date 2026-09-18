from __future__ import annotations

import time

from app.db import session_scope
from app.models import Task


def wait_for_status(client, task_id: str, statuses: set[str], timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    last: dict = {}
    while time.time() < deadline:
        last = client.get(f"/api/tasks/{task_id}").json()
        if last.get("status") in statuses:
            return last
        time.sleep(0.05)
    return last


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["agents"] > 0


def test_runtime_settings_shows_mock_when_unconfigured(client):
    response = client.get("/api/settings/runtime")
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "mock"
    assert body["configured"] is False
    assert body["mock_mode"] is True


def test_full_task_lifecycle_completes_with_mock_provider(client):
    project = client.post("/api/projects", json={"name": "Demo project"}).json()

    task = client.post(
        "/api/tasks",
        json={"project_id": project["id"], "input_text": "Fix a bug in the backend API and add tests"},
    ).json()
    assert task["status"] in {"queued", "running", "completed"}

    final = wait_for_status(client, task["id"], {"completed", "failed"})
    assert final["status"] == "completed"
    assert final["final_answer"]
    roles = {run["role"] for run in final["runs"]}
    assert {"agent", "critic", "synthesis"}.issubset(roles)


def test_task_retry_after_forced_failure(client):
    project = client.post("/api/projects", json={"name": "Retry project"}).json()
    task = client.post(
        "/api/tasks",
        json={"project_id": project["id"], "input_text": "Analyse sales pipeline performance"},
    ).json()
    wait_for_status(client, task["id"], {"completed", "failed"})

    with session_scope() as db:
        db_task = db.get(Task, task["id"])
        db_task.status = "failed"
        db_task.error_message = "forced failure for test"
        db.commit()

    retried = client.post(f"/api/tasks/{task['id']}/retry").json()
    assert retried["status"] in {"queued", "running", "completed"}

    final = wait_for_status(client, task["id"], {"completed", "failed"})
    assert final["status"] == "completed"
    assert final["attempt"] >= 2


def test_task_cancel_rejected_when_already_completed(client):
    project = client.post("/api/projects", json={"name": "Cancel project"}).json()
    task = client.post(
        "/api/tasks",
        json={"project_id": project["id"], "input_text": "Summarize research findings"},
    ).json()
    wait_for_status(client, task["id"], {"completed", "failed"})

    response = client.post(f"/api/tasks/{task['id']}/cancel")
    assert response.status_code == 400


def test_russian_beverage_task_exposes_routing_plan_and_finance(client):
    project = client.post("/api/projects", json={"name": "Напитки"}).json()
    task = client.post(
        "/api/tasks",
        json={
            "project_id": project["id"],
            "input_text": (
                "Рассчитай рецептуру молочного лимонада на 1000 литров, "
                "Брикс 4.8-4.9, проверь себестоимость и риски производства"
            ),
        },
    ).json()
    final = wait_for_status(client, task["id"], {"completed", "failed"})
    assert final["status"] == "completed"
    divisions = {run["division"] for run in final["runs"] if run["role"] == "agent"}
    assert "finance" in divisions
    assert divisions.intersection({"engineering", "product", "specialized"})
    levels = {event["level"] for event in final["events"]}
    assert "routing" in levels
    assert "plan" in levels
    assert "stage" in levels
    assert final["final_answer"]


def test_retry_replaces_stale_runs_without_duplicating_artifacts(client):
    project = client.post("/api/projects", json={"name": "Retry clean"}).json()
    task = client.post(
        "/api/tasks",
        json={"project_id": project["id"], "input_text": "Проверь себестоимость напитка"},
    ).json()
    first = wait_for_status(client, task["id"], {"completed", "failed"})
    assert first["status"] == "completed"
    first_agent_ids = [run["agent_id"] for run in first["runs"] if run["role"] == "agent"]

    with session_scope() as db:
        db_task = db.get(Task, task["id"])
        db_task.status = "failed"
        db_task.error_message = "forced retry"
        db.commit()

    response = client.post(f"/api/tasks/{task['id']}/retry")
    assert response.status_code == 200
    second = wait_for_status(client, task["id"], {"completed", "failed"})
    assert second["status"] == "completed"
    second_agent_ids = [run["agent_id"] for run in second["runs"] if run["role"] == "agent"]
    assert second_agent_ids == first_agent_ids
    assert len(second_agent_ids) == len(set(second_agent_ids))
