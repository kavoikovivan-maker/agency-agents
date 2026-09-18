from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..files import extract_text, save_upload, validate_upload
from ..models import Artifact, Project
from ..schemas import ArtifactOut
from ..security import require_session, safe_join, sanitize_filename

router = APIRouter(prefix="/api/files", tags=["files"])


@router.post("", response_model=ArtifactOut)
async def upload_file(
    project_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: None = Depends(require_session),
):
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    safe_name = sanitize_filename(file.filename or "upload.bin")
    validate_upload(safe_name, 0)  # extension check up front

    project_dir = settings.uploads_dir / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    dest = safe_join(project_dir, stored_name)

    size = await save_upload(file, dest)
    validate_upload(safe_name, size)

    text, error = extract_text(dest)
    artifact = Artifact(
        project_id=project_id,
        filename=safe_name,
        stored_path=str(dest.relative_to(settings.data_dir)),
        content_type=file.content_type or "",
        size=size,
        extracted_text=text,
        extraction_error=error,
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact


@router.get("", response_model=list[ArtifactOut])
def list_files(project_id: str, db: Session = Depends(get_db), _: None = Depends(require_session)):
    return db.query(Artifact).filter(Artifact.project_id == project_id).order_by(Artifact.created_at.desc()).all()
