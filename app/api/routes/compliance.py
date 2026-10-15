from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.dependencies import get_db, get_current_user
from app.database.models import ComplianceFinding, DrawingAnalysis, ExtractedAnnotation, SpecificationRequirement, User
from app.schemas.compliance import ComplianceFindingResponse, ComplianceSummaryResponse
from app.schemas.common import APIResponse
from app.services.compliance_engine import compliance_engine
from app.services.retrieval_service import retrieval_service

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/project/{project_id}", response_model=APIResponse[ComplianceSummaryResponse])
def get_project_compliance_summary(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    findings = db.query(ComplianceFinding).filter(
        ComplianceFinding.project_id == project_id
    ).order_by(ComplianceFinding.created_at.desc()).all()

    total = len(findings)
    passed = sum(1 for f in findings if f.outcome == "pass")
    failed = sum(1 for f in findings if f.outcome == "fail")
    needs_review = sum(1 for f in findings if f.outcome == "needs_review")
    not_evaluable = sum(1 for f in findings if f.outcome == "not_evaluable")
    crit_errors = sum(1 for f in findings if f.severity == "error")
    warnings = sum(1 for f in findings if f.severity == "warning")

    findings_resp = []
    for f in findings:
        ann_text = f.annotation.original_text if f.annotation else None
        req_code = f.requirement.requirement_code if f.requirement else None
        findings_resp.append(ComplianceFindingResponse(
            id=f.id,
            analysis_id=f.analysis_id,
            project_id=f.project_id,
            annotation_id=f.annotation_id,
            requirement_id=f.requirement_id,
            rule_identifier=f.rule_identifier,
            finding_type=f.finding_type,
            severity=f.severity,
            outcome=f.outcome,
            expected_value=f.expected_value,
            observed_value=f.observed_value,
            deviation_value=f.deviation_value,
            rule_version=f.rule_version,
            explanation=f.explanation,
            review_status=f.review_status,
            evidence_json=f.evidence_json,
            annotation_text=ann_text,
            requirement_code=req_code,
            created_at=f.created_at
        ))

    summary = ComplianceSummaryResponse(
        total_findings=total,
        passed=passed,
        failed=failed,
        needs_review=needs_review,
        not_evaluable=not_evaluable,
        critical_errors=crit_errors,
        warnings=warnings,
        findings=findings_resp
    )
    return APIResponse(data=summary)


@router.post("/project/{project_id}/re-evaluate", response_model=APIResponse[ComplianceSummaryResponse])
def re_evaluate_project_compliance(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Re-runs deterministic compliance engine on all annotations in the project
    against current specification requirements.
    """
    latest_analysis = db.query(DrawingAnalysis).filter(
        DrawingAnalysis.project_id == project_id
    ).order_by(DrawingAnalysis.created_at.desc()).first()

    if not latest_analysis:
        raise HTTPException(status_code=400, detail="No completed drawing analysis found for this project.")

    # Remove previous findings for this analysis
    db.query(ComplianceFinding).filter(ComplianceFinding.analysis_id == latest_analysis.id).delete()
    db.commit()

    annotations = db.query(ExtractedAnnotation).filter(
        ExtractedAnnotation.analysis_id == latest_analysis.id,
        ExtractedAnnotation.verification_status != "rejected"
    ).all()

    for ann in annotations:
        matched_reqs = retrieval_service.find_matching_requirements(
            db=db,
            project_id=project_id,
            dimension_type=ann.dimension_type,
            nominal_value=ann.nominal_value,
            unit=ann.unit
        )

        for req in matched_reqs:
            findings = compliance_engine.evaluate_annotation_against_requirement(ann, req)
            for f in findings:
                finding_obj = ComplianceFinding(
                    analysis_id=latest_analysis.id,
                    project_id=project_id,
                    annotation_id=ann.id,
                    requirement_id=req.id,
                    rule_identifier=f["rule_identifier"],
                    finding_type=f["finding_type"],
                    severity=f["severity"],
                    outcome=f["outcome"],
                    expected_value=f.get("expected_value"),
                    observed_value=f.get("observed_value"),
                    deviation_value=f.get("deviation_value"),
                    rule_version=f.get("rule_version", "1.0.0"),
                    explanation=f["explanation"],
                    review_status="unresolved",
                    evidence_json=f.get("evidence")
                )
                db.add(finding_obj)

    db.commit()
    return get_project_compliance_summary(project_id=project_id, db=db, current_user=current_user)
