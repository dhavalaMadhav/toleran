from typing import Optional
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.dependencies import get_db, get_current_user_optional
from app.database.models import (
    Project, Document, DrawingAnalysis, DrawingPage,
    ExtractedAnnotation, ComplianceFinding, ProcessingJob,
    SpecificationRequirement, ReviewDecision, User
)

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def index_redirect():
    return RedirectResponse(url="/dashboard", status_code=302)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={})


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    total_projects = db.query(Project).filter(Project.status != "archived").count()
    total_drawings = db.query(Document).filter(Document.file_type == "drawing").count()
    completed_analyses = db.query(DrawingAnalysis).filter(DrawingAnalysis.status.in_(["completed", "needs_review"])).count()
    pending_reviews = db.query(ExtractedAnnotation).filter(
        ExtractedAnnotation.verification_status.in_(["pending_review", "rejected"])
    ).count()

    findings_error = db.query(ComplianceFinding).filter(ComplianceFinding.severity == "error").count()
    findings_warning = db.query(ComplianceFinding).filter(ComplianceFinding.severity == "warning").count()
    findings_info = db.query(ComplianceFinding).filter(ComplianceFinding.severity == "info").count()

    recent_projects = db.query(Project).order_by(Project.updated_at.desc()).limit(6).all()
    recent_analyses = db.query(DrawingAnalysis).order_by(DrawingAnalysis.created_at.desc()).limit(6).all()
    failed_jobs = db.query(ProcessingJob).filter(ProcessingJob.status == "failed").order_by(ProcessingJob.created_at.desc()).limit(5).all()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "current_user": current_user,
            "stats": {
                "total_projects": total_projects,
                "total_drawings": total_drawings,
                "completed_analyses": completed_analyses,
                "pending_reviews": pending_reviews,
                "findings_error": findings_error,
                "findings_warning": findings_warning,
                "findings_info": findings_info
            },
            "recent_projects": recent_projects,
            "recent_analyses": recent_analyses,
            "failed_jobs": failed_jobs
        }
    )


@router.get("/projects", response_class=HTMLResponse)
def projects_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    projects = db.query(Project).filter(Project.status != "archived").order_by(Project.created_at.desc()).all()
    return templates.TemplateResponse(
        request=request,
        name="projects.html",
        context={
            "current_user": current_user,
            "projects": projects
        }
    )


@router.get("/projects/{project_id}", response_class=HTMLResponse)
def project_detail_page(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    drawings = db.query(Document).filter(
        Document.project_id == project_id,
        Document.file_type.in_(["drawing", "cad"])
    ).order_by(Document.created_at.desc()).all()

    specs = db.query(Document).filter(
        Document.project_id == project_id,
        Document.file_type == "specification"
    ).order_by(Document.created_at.desc()).all()

    analyses = db.query(DrawingAnalysis).filter(
        DrawingAnalysis.project_id == project_id
    ).order_by(DrawingAnalysis.created_at.desc()).all()

    findings = db.query(ComplianceFinding).filter(
        ComplianceFinding.project_id == project_id
    ).all()

    pending_count = db.query(ExtractedAnnotation).join(ExtractedAnnotation.analysis).filter(
        ExtractedAnnotation.analysis.has(project_id=project_id),
        ExtractedAnnotation.verification_status.in_(["pending_review", "rejected"])
    ).count()

    latest_analysis = analyses[0] if analyses else None

    return templates.TemplateResponse(
        request=request,
        name="project_detail.html",
        context={
            "current_user": current_user,
            "project": project,
            "drawings": drawings,
            "specifications": specs,
            "analyses": analyses,
            "latest_analysis": latest_analysis,
            "findings_count": len(findings),
            "pending_count": pending_count
        }
    )


@router.get("/projects/{project_id}/analysis/{analysis_id}", response_class=HTMLResponse)
def drawing_analysis_page(
    project_id: int,
    analysis_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    analysis = db.query(DrawingAnalysis).filter(
        DrawingAnalysis.id == analysis_id,
        DrawingAnalysis.project_id == project_id
    ).first()
    if not project or not analysis:
        raise HTTPException(status_code=404, detail="Project or Analysis record not found.")

    pages = db.query(DrawingPage).filter(
        DrawingPage.analysis_id == analysis_id
    ).order_by(DrawingPage.page_number.asc()).all()

    annotations = db.query(ExtractedAnnotation).filter(
        ExtractedAnnotation.analysis_id == analysis_id
    ).order_by(ExtractedAnnotation.page_number.asc(), ExtractedAnnotation.id.asc()).all()

    findings = db.query(ComplianceFinding).filter(
        ComplianceFinding.analysis_id == analysis_id
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="drawing_analysis.html",
        context={
            "current_user": current_user,
            "project": project,
            "analysis": analysis,
            "pages": pages,
            "annotations": annotations,
            "findings": findings
        }
    )


@router.get("/projects/{project_id}/specifications", response_class=HTMLResponse)
def specifications_page(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    spec_docs = db.query(Document).filter(
        Document.project_id == project_id,
        Document.file_type == "specification"
    ).all()

    requirements = db.query(SpecificationRequirement).filter(
        SpecificationRequirement.project_id == project_id
    ).order_by(SpecificationRequirement.requirement_code.asc()).all()

    return templates.TemplateResponse(
        request=request,
        name="specifications.html",
        context={
            "current_user": current_user,
            "project": project,
            "spec_docs": spec_docs,
            "requirements": requirements
        }
    )


@router.get("/projects/{project_id}/copilot", response_class=HTMLResponse)
def copilot_page(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    conversations = db.query(Project).filter(Project.id == project_id).first().conversations

    return templates.TemplateResponse(
        request=request,
        name="copilot.html",
        context={
            "current_user": current_user,
            "project": project,
            "conversations": conversations
        }
    )


@router.get("/projects/{project_id}/review", response_class=HTMLResponse)
def review_page(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    pending_annotations = db.query(ExtractedAnnotation).join(ExtractedAnnotation.analysis).filter(
        ExtractedAnnotation.analysis.has(project_id=project_id),
        ExtractedAnnotation.verification_status.in_(["pending_review", "rejected"])
    ).all()

    unresolved_findings = db.query(ComplianceFinding).filter(
        ComplianceFinding.project_id == project_id,
        ComplianceFinding.review_status == "unresolved"
    ).all()

    decisions = db.query(ReviewDecision).filter(
        ReviewDecision.project_id == project_id
    ).order_by(ReviewDecision.created_at.desc()).limit(25).all()

    return templates.TemplateResponse(
        request=request,
        name="review.html",
        context={
            "current_user": current_user,
            "project": project,
            "pending_annotations": pending_annotations,
            "unresolved_findings": unresolved_findings,
            "decisions": decisions
        }
    )


@router.get("/projects/{project_id}/reports", response_class=HTMLResponse)
def reports_page(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    analyses = db.query(DrawingAnalysis).filter(
        DrawingAnalysis.project_id == project_id
    ).order_by(DrawingAnalysis.created_at.desc()).all()

    findings = db.query(ComplianceFinding).filter(
        ComplianceFinding.project_id == project_id
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="reports.html",
        context={
            "current_user": current_user,
            "project": project,
            "analyses": analyses,
            "findings": findings
        }
    )
