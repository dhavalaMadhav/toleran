from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from app.dependencies import get_db, get_current_user
from app.database.models import Document, ProcessingJob, DrawingAnalysis, DrawingPage, ExtractedAnnotation, GeometricFeature, ComplianceFinding, User
from app.schemas.common import APIResponse
from app.agents.workflow import workflow_orchestrator

router = APIRouter(prefix="/analysis", tags=["analysis"])


def _run_background_pipeline(job_id: int):
    from app.database.session import SessionLocal
    db = SessionLocal()
    try:
        workflow_orchestrator.run_pipeline(db, job_id)
    finally:
        db.close()


@router.post("/start", response_model=APIResponse[Dict[str, Any]], status_code=status.HTTP_202_ACCEPTED)
def start_drawing_analysis(
    document_id: int,
    background_tasks: BackgroundTasks,
    run_sync: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    if doc.file_type != "drawing":
        raise HTTPException(status_code=400, detail="Only drawing documents can be analyzed for dimensions and compliance.")

    # Create job record
    job = ProcessingJob(
        document_id=doc.id,
        project_id=doc.project_id,
        stage="queued",
        status="queued",
        progress_pct=0
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    if run_sync:
        # Run synchronously (ideal for integration tests or quick drawings)
        workflow_orchestrator.run_pipeline(db, job.id)
        latest_analysis = db.query(DrawingAnalysis).filter(
            DrawingAnalysis.document_id == doc.id
        ).order_by(DrawingAnalysis.created_at.desc()).first()

        return APIResponse(
            message="Analysis completed synchronously",
            data={
                "job_id": job.id,
                "status": job.status,
                "analysis_id": latest_analysis.id if latest_analysis else None
            }
        )
    else:
        # Background task
        background_tasks.add_task(_run_background_pipeline, job.id)
        return APIResponse(
            message="Analysis queued for background processing",
            data={"job_id": job.id, "status": "queued"}
        )


@router.get("/jobs/{job_id}", response_model=APIResponse[Dict[str, Any]])
def get_job_status(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    analysis_id = None
    if job.status in ("completed", "needs_review"):
        analysis = db.query(DrawingAnalysis).filter(
            DrawingAnalysis.document_id == job.document_id
        ).order_by(DrawingAnalysis.created_at.desc()).first()
        if analysis:
            analysis_id = analysis.id

    return APIResponse(data={
        "job_id": job.id,
        "document_id": job.document_id,
        "project_id": job.project_id,
        "stage": job.stage,
        "status": job.status,
        "progress_pct": job.progress_pct,
        "error_message": job.error_message,
        "execution_time_sec": job.execution_time_sec,
        "analysis_id": analysis_id
    })


@router.get("/{analysis_id}", response_model=APIResponse[Dict[str, Any]])
def get_analysis_details(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    analysis = db.query(DrawingAnalysis).filter(DrawingAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis record not found.")

    pages = db.query(DrawingPage).filter(DrawingPage.analysis_id == analysis_id).order_by(DrawingPage.page_number.asc()).all()
    annotations = db.query(ExtractedAnnotation).filter(ExtractedAnnotation.analysis_id == analysis_id).all()
    findings = db.query(ComplianceFinding).filter(ComplianceFinding.analysis_id == analysis_id).all()
    features = db.query(GeometricFeature).filter(GeometricFeature.analysis_id == analysis_id).all()

    pages_data = [
        {
            "id": p.id,
            "page_number": p.page_number,
            "width_pt": p.width_pt,
            "height_pt": p.height_pt,
            "render_width_px": p.render_width_px,
            "render_height_px": p.render_height_px,
            "render_image_url": f"/static/{p.render_image_path.replace('\\', '/')}" if p.render_image_path else ""
        }
        for p in pages
    ]

    annotations_data = [
        {
            "id": a.id,
            "page_id": a.page_id,
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
            "bbox": {
                "x0": a.bbox_x0,
                "y0": a.bbox_y0,
                "x1": a.bbox_x1,
                "y1": a.bbox_y1
            },
            "crop_image_url": f"/static/{a.crop_image_path.replace('\\', '/')}" if a.crop_image_path else None,
            "confidence": a.confidence,
            "is_ambiguous": a.is_ambiguous,
            "ambiguity_reason": a.ambiguity_reason,
            "verification_status": a.verification_status,
            "extraction_method": a.extraction_method
        }
        for a in annotations
    ]

    findings_data = [
        {
            "id": f.id,
            "annotation_id": f.annotation_id,
            "requirement_id": f.requirement_id,
            "rule_identifier": f.rule_identifier,
            "finding_type": f.finding_type,
            "severity": f.severity,
            "outcome": f.outcome,
            "expected_value": f.expected_value,
            "observed_value": f.observed_value,
            "deviation_value": f.deviation_value,
            "explanation": f.explanation,
            "review_status": f.review_status,
            "evidence": f.evidence_json
        }
        for f in findings
    ]

    features_data = [
        {
            "id": ft.id,
            "feature_type": ft.feature_type,
            "center_x": ft.center_x,
            "center_y": ft.center_y,
            "radius": ft.radius,
            "bbox": {
                "x0": ft.bbox_x0,
                "y0": ft.bbox_y0,
                "x1": ft.bbox_x1,
                "y1": ft.bbox_y1
            }
        }
        for ft in features
    ]

    return APIResponse(data={
        "id": analysis.id,
        "document_id": analysis.document_id,
        "project_id": analysis.project_id,
        "status": analysis.status,
        "pipeline_version": analysis.pipeline_version,
        "summary": analysis.summary_json,
        "pages": pages_data,
        "annotations": annotations_data,
        "findings": findings_data,
        "features": features_data
    })
