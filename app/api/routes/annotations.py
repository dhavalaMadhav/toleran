from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.dependencies import get_db, get_current_user
from app.database.models import ExtractedAnnotation, ReviewDecision, User
from app.schemas.annotation import AnnotationCorrectionRequest, ExtractedAnnotationResponse
from app.schemas.common import APIResponse

router = APIRouter(prefix="/annotations", tags=["annotations"])


@router.get("/{annotation_id}", response_model=APIResponse[ExtractedAnnotationResponse])
def get_annotation(
    annotation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ann = db.query(ExtractedAnnotation).filter(ExtractedAnnotation.id == annotation_id).first()
    if not ann:
        raise HTTPException(status_code=404, detail="Annotation not found.")
    return APIResponse(data=ExtractedAnnotationResponse.model_validate(ann))


@router.patch("/{annotation_id}/correct", response_model=APIResponse[ExtractedAnnotationResponse])
def correct_annotation(
    annotation_id: int,
    data: AnnotationCorrectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ann = db.query(ExtractedAnnotation).filter(ExtractedAnnotation.id == annotation_id).first()
    if not ann:
        raise HTTPException(status_code=404, detail="Annotation not found.")

    prev_state = {
        "nominal_value": ann.nominal_value,
        "dimension_type": ann.dimension_type,
        "upper_deviation": ann.upper_deviation,
        "lower_deviation": ann.lower_deviation,
        "verification_status": ann.verification_status
    }

    if data.nominal_value is not None:
        ann.nominal_value = data.nominal_value
    if data.dimension_type is not None:
        ann.dimension_type = data.dimension_type
    if data.unit is not None:
        ann.unit = data.unit
    if data.upper_deviation is not None:
        ann.upper_deviation = data.upper_deviation
    if data.lower_deviation is not None:
        ann.lower_deviation = data.lower_deviation
    if data.tolerance_type is not None:
        ann.tolerance_type = data.tolerance_type

    # Recompute min and max limits
    if ann.nominal_value is not None:
        u_dev = ann.upper_deviation or 0.0
        l_dev = ann.lower_deviation or 0.0
        ann.min_val = round(ann.nominal_value + l_dev, 4)
        ann.max_val = round(ann.nominal_value + u_dev, 4)

    ann.verification_status = data.verification_status or "corrected"
    ann.reviewed_by_id = current_user.id
    ann.reviewed_at = datetime.now(timezone.utc)
    ann.reviewer_notes = data.notes

    new_state = {
        "nominal_value": ann.nominal_value,
        "dimension_type": ann.dimension_type,
        "upper_deviation": ann.upper_deviation,
        "lower_deviation": ann.lower_deviation,
        "verification_status": ann.verification_status,
        "notes": data.notes
    }

    # Record audit review decision
    decision = ReviewDecision(
        project_id=ann.analysis.project_id,
        target_type="annotation",
        target_id=ann.id,
        decision="modified",
        previous_state_json=prev_state,
        new_state_json=new_state,
        reviewer_id=current_user.id,
        notes=data.notes
    )
    db.add(decision)
    db.commit()
    db.refresh(ann)

    return APIResponse(
        message="Annotation corrected and verified by engineer",
        data=ExtractedAnnotationResponse.model_validate(ann)
    )


@router.post("/{annotation_id}/reject", response_model=APIResponse[ExtractedAnnotationResponse])
def reject_annotation(
    annotation_id: int,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ann = db.query(ExtractedAnnotation).filter(ExtractedAnnotation.id == annotation_id).first()
    if not ann:
        raise HTTPException(status_code=404, detail="Annotation not found.")

    ann.verification_status = "rejected"
    ann.reviewed_by_id = current_user.id
    ann.reviewed_at = datetime.now(timezone.utc)
    ann.reviewer_notes = notes or "Rejected as spurious OCR detection."

    decision = ReviewDecision(
        project_id=ann.analysis.project_id,
        target_type="annotation",
        target_id=ann.id,
        decision="rejected",
        previous_state_json={"status": ann.verification_status},
        new_state_json={"status": "rejected"},
        reviewer_id=current_user.id,
        notes=notes
    )
    db.add(decision)
    db.commit()
    db.refresh(ann)

    return APIResponse(
        message="Annotation rejected from engineering model",
        data=ExtractedAnnotationResponse.model_validate(ann)
    )
