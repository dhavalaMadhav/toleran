from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.dependencies import get_db, get_current_user
from app.database.models import Project, Document, ComplianceFinding, User
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.schemas.common import APIResponse

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=APIResponse[List[ProjectResponse]])
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    projects = db.query(Project).filter(Project.status != "archived").order_by(Project.created_at.desc()).all()
    results = []
    for p in projects:
        d_count = db.query(Document).filter(Document.project_id == p.id, Document.file_type == "drawing").count()
        s_count = db.query(Document).filter(Document.project_id == p.id, Document.file_type == "specification").count()
        unresolved_count = db.query(ComplianceFinding).filter(
            ComplianceFinding.project_id == p.id,
            ComplianceFinding.review_status == "unresolved",
            ComplianceFinding.outcome.in_(["fail", "needs_review"])
        ).count()

        p_resp = ProjectResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            part_number=p.part_number,
            revision=p.revision,
            status=p.status,
            created_at=p.created_at,
            updated_at=p.updated_at,
            drawing_count=d_count,
            spec_count=s_count,
            unresolved_findings_count=unresolved_count
        )
        results.append(p_resp)

    return APIResponse(data=results)


@router.post("", response_model=APIResponse[ProjectResponse], status_code=status.HTTP_201_CREATED)
def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = Project(
        name=data.name,
        description=data.description,
        part_number=data.part_number,
        revision=data.revision or "Rev A",
        status="active",
        created_by_id=current_user.id
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    return APIResponse(
        message="Project created successfully",
        data=ProjectResponse.model_validate(project)
    )


@router.get("/{project_id}", response_model=APIResponse[ProjectResponse])
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found.")

    d_count = db.query(Document).filter(Document.project_id == p.id, Document.file_type == "drawing").count()
    s_count = db.query(Document).filter(Document.project_id == p.id, Document.file_type == "specification").count()
    unresolved_count = db.query(ComplianceFinding).filter(
        ComplianceFinding.project_id == p.id,
        ComplianceFinding.review_status == "unresolved"
    ).count()

    resp = ProjectResponse(
        id=p.id,
        name=p.name,
        description=p.description,
        part_number=p.part_number,
        revision=p.revision,
        status=p.status,
        created_at=p.created_at,
        updated_at=p.updated_at,
        drawing_count=d_count,
        spec_count=s_count,
        unresolved_findings_count=unresolved_count
    )
    return APIResponse(data=resp)


@router.patch("/{project_id}", response_model=APIResponse[ProjectResponse])
def update_project(
    project_id: int,
    data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found.")

    if data.name is not None:
        p.name = data.name
    if data.description is not None:
        p.description = data.description
    if data.part_number is not None:
        p.part_number = data.part_number
    if data.revision is not None:
        p.revision = data.revision
    if data.status is not None:
        p.status = data.status

    db.commit()
    db.refresh(p)
    return APIResponse(message="Project updated", data=ProjectResponse.model_validate(p))
