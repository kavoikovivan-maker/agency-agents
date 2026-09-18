"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AgentInfo(BaseModel):
    id: str
    division: str
    name: str
    description: str
    path: str


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ProjectOut(BaseModel):
    id: str
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationCreate(BaseModel):
    title: str = ""


class ConversationOut(BaseModel):
    id: str
    project_id: str
    title: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    project_id: str
    conversation_id: str | None = None
    input_text: str = Field(min_length=1)
    file_ids: list[str] = Field(default_factory=list)


class TaskRunOut(BaseModel):
    id: str
    agent_id: str
    division: str
    role: str
    step_order: int
    status: str
    input_text: str
    output_text: str
    error_message: str
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class EventOut(BaseModel):
    level: str
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskOut(BaseModel):
    id: str
    project_id: str
    conversation_id: str | None
    input_text: str
    status: str
    classification: str
    final_answer: str
    error_message: str
    attempt: int
    created_at: datetime
    updated_at: datetime
    runs: list[TaskRunOut] = Field(default_factory=list)
    events: list[EventOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ArtifactOut(BaseModel):
    id: str
    filename: str
    content_type: str
    size: int
    extraction_error: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RuntimeSettingsOut(BaseModel):
    provider: str
    model: str
    configured: bool
    mock_mode: bool
    agent_count: int
    max_agents_per_task: int
    max_upload_mb: int
