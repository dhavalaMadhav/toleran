from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.dependencies import get_db, get_current_user
from app.database.models import SpecificationRequirement, Document, User
from app.schemas.specification import RequirementResponse, RequirementCreate
from app.schemas.common import APIResponse

router = APIRouter(prefix="/specifications", tags=["specifications"])


@router.get("/project/{project_id}", response_model=APIResponse[List[RequirementResponse]])
def list_project_requirements(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    reqs = db.query(SpecificationRequirement).filter(
        SpecificationRequirement.project_id == project_id
    ).order_by(SpecificationRequirement.requirement_code.asc()).all()

    return APIResponse(data=[RequirementResponse.model_validate(r) for r in reqs])


@router.post("/project/{project_id}", response_model=APIResponse[RequirementResponse], status_code=status.HTTP_201_CREATED)
def create_manual_requirement(
    project_id: int,
    data: RequirementCreate,
    document_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not document_id:
        # Link to first spec document in project or create placeholder
        doc = db.query(Document).filter(
            Document.project_id == project_id,
            Document.file_type == "specification"
        ).first()
        if not doc:
            doc = db.query(Document).filter(Document.project_id == project_id).first()
        if not doc:
            raise HTTPException(status_code=400, detail="Please upload a specification or drawing document first.")
        document_id = doc.id

    req = SpecificationRequirement(
        document_id=document_id,
        project_id=project_id,
        requirement_code=data.requirement_code,
        title=data.title,
        requirement_type=data.requirement_type,
        nominal_value=data.nominal_value,
        unit=data.unit,
        min_val=data.min_val,
        max_val=data.max_val,
        tolerance_rule=data.tolerance_rule,
        raw_text=data.raw_text,
        page_number=data.page_number,
        section=data.section,
        confidence=1.0
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    return APIResponse(
        message="Engineering requirement added successfully",
        data=RequirementResponse.model_validate(req)
    )
