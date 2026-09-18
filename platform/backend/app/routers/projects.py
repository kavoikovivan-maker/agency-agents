from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Conversation, Project
from ..schemas import ConversationCreate, ConversationOut, ProjectCreate, ProjectOut
from ..security import require_session

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db), _: None = Depends(require_session)):
    return db.scalars(select(Project).order_by(Project.created_at.desc())).all()


@router.post("", response_model=ProjectOut)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db), _: None = Depends(require_session)):
    project = Project(name=payload.name)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}/conversations", response_model=list[ConversationOut])
def list_conversations(project_id: str, db: Session = Depends(get_db), _: None = Depends(require_session)):
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return db.scalars(
        select(Conversation).where(Conversation.project_id == project_id).order_by(Conversation.created_at.desc())
    ).all()


@router.post("/{project_id}/conversations", response_model=ConversationOut)
def create_conversation(project_id: str, payload: ConversationCreate, db: Session = Depends(get_db), _: None = Depends(require_session)):
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    conversation = Conversation(project_id=project_id, title=payload.title)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation
