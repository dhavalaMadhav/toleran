from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.dependencies import get_db, get_current_user
from app.database.models import ExtractedAnnotation, ComplianceFinding, ReviewDecision, User
from app.schemas.review import ReviewActionRequest, ReviewDecisionResponse
from app.schemas.common import APIResponse

router = APIRouter(prefix="/review", tags=["review"])


@router.get("/queue/{project_id}", response_model=APIResponse[Dict[str, Any]])
def get_review_queue(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns items requiring human engineering review:
    1. Annotations marked pending_review or ambiguous
    2. Compliance findings with status needs_review or fail
    """
    annotations = db.query(ExtractedAnnotation).join(ExtractedAnnotation.analysis).filter(
        ExtractedAnnotation.analysis.has(project_id=project_id),
        ExtractedAnnotation.verification_status.in_(["pending_review", "rejected"])
    ).all()

    findings = db.query(ComplianceFinding).filter(
        ComplianceFinding.project_id == project_id,
        ComplianceFinding.review_status == "unresolved",
        ComplianceFinding.outcome.in_(["fail", "needs_review"])
    ).all()

    recent_decisions = db.query(ReviewDecision).filter(
        ReviewDecision.project_id == project_id
    ).order_by(ReviewDecision.created_at.desc()).limit(20).all()

    return APIResponse(data={
        "pending_annotations": [
            {
                "id": a.id,
                "analysis_id": a.analysis_id,
                "page_number": a.page_number,
                "original_text": a.original_text,
                "dimension_type": a.dimension_type,
                "nominal_value": a.nominal_value,
                "unit": a.unit,
                "upper_deviation": a.upper_deviation,
                "lower_deviation": a.lower_deviation,
                "min_val": a.min_val,
                "max_val": a.max_val,
                "tolerance_type": a.tolerance_type,
                "confidence": a.confidence,
                "is_ambiguous": a.is_ambiguous,
                "ambiguity_reason": a.ambiguity_reason,
                "verification_status": a.verification_status,
                "crop_image_url": f"/static/{a.crop_image_path.replace('\\', '/')}" if a.crop_image_path else None
            }
            for a in annotations
        ],
        "pending_findings": [
            {
                "id": f.id,
                "annotation_id": f.annotation_id,
                "rule_identifier": f.rule_identifier,
                "finding_type": f.finding_type,
                "severity": f.severity,
                "outcome": f.outcome,
                "expected_value": f.expected_value,
                "observed_value": f.observed_value,
                "explanation": f.explanation,
                "annotation_text": f.annotation.original_text if f.annotation else None
            }
            for f in findings
        ],
        "recent_decisions": [
            {
                "id": d.id,
                "target_type": d.target_type,
                "target_id": d.target_id,
                "decision": d.decision,
                "reviewer_name": d.reviewer.full_name if d.reviewer else "Engineer",
                "notes": d.notes,
                "created_at": d.created_at
            }
            for d in recent_decisions
        ]
    })


@router.post("/annotation/{annotation_id}", response_model=APIResponse[Dict[str, Any]])
def submit_annotation_review(
    annotation_id: int,
    action: ReviewActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ann = db.query(ExtractedAnnotation).filter(ExtractedAnnotation.id == annotation_id).first()
    if not ann:
        raise HTTPException(status_code=404, detail="Annotation not found.")

    prev_status = ann.verification_status
    if action.decision == "approved":
        ann.verification_status = "approved"
    elif action.decision == "rejected":
        ann.verification_status = "rejected"
    elif action.decision == "modified":
        ann.verification_status = "corrected"
        if action.override_values:
            if "nominal_value" in action.override_values:
                ann.nominal_value = float(action.override_values["nominal_value"])
            if "dimension_type" in action.override_values:
                ann.dimension_type = action.override_values["dimension_type"]
            if "unit" in action.override_values:
                ann.unit = action.override_values["unit"]
            if "upper_deviation" in action.override_values:
                ann.upper_deviation = float(action.override_values["upper_deviation"])
            if "lower_deviation" in action.override_values:
                ann.lower_deviation = float(action.override_values["lower_deviation"])
            if ann.nominal_value is not None:
                ann.min_val = round(ann.nominal_value + (ann.lower_deviation or 0.0), 4)
                ann.max_val = round(ann.nominal_value + (ann.upper_deviation or 0.0), 4)

    ann.reviewed_by_id = current_user.id
    ann.reviewed_at = datetime.now(timezone.utc)
    ann.reviewer_notes = action.notes

    decision = ReviewDecision(
        project_id=ann.analysis.project_id,
        target_type="annotation",
        target_id=ann.id,
        decision=action.decision,
        previous_state_json={"status": prev_status},
        new_state_json={"status": ann.verification_status, "overrides": action.override_values},
        reviewer_id=current_user.id,
        notes=action.notes
    )
    db.add(decision)
    db.commit()

    return APIResponse(
        message=f"Annotation decision '{action.decision}' saved.",
        data={"annotation_id": ann.id, "status": ann.verification_status}
    )


@router.post("/finding/{finding_id}", response_model=APIResponse[Dict[str, Any]])
def submit_finding_review(
    finding_id: int,
    action: ReviewActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    finding = db.query(ComplianceFinding).filter(ComplianceFinding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Compliance finding not found.")

    prev_status = finding.review_status
    if action.decision in ("approved", "approved_deviation"):
        finding.review_status = "approved_deviation"
    elif action.decision == "waived":
        finding.review_status = "waived"
    elif action.decision == "remediated":
        finding.review_status = "remediated"

    finding.reviewed_by_id = current_user.id
    finding.reviewed_at = datetime.now(timezone.utc)

    decision = ReviewDecision(
        project_id=finding.project_id,
        target_type="finding",
        target_id=finding.id,
        decision=action.decision,
        previous_state_json={"review_status": prev_status},
        new_state_json={"review_status": finding.review_status},
        reviewer_id=current_user.id,
        notes=action.notes
    )
    db.add(decision)
    db.commit()

    return APIResponse(
        message=f"Finding resolution '{finding.review_status}' recorded by engineer.",
        data={"finding_id": finding.id, "review_status": finding.review_status}
    )
