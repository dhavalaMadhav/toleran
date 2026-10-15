from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.dependencies import get_db, get_current_user
from app.database.models import DrawingAnalysis, User
from app.services.report_service import report_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/csv/{project_id}/{analysis_id}")
def download_csv_report(
    project_id: int,
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    analysis = db.query(DrawingAnalysis).filter(
        DrawingAnalysis.id == analysis_id,
        DrawingAnalysis.project_id == project_id
    ).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis record not found.")

    csv_content = report_service.generate_csv_report(db, project_id, analysis_id)
    filename = f"compliance_export_proj{project_id}_analysis{analysis_id}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/pdf/{project_id}/{analysis_id}")
def download_pdf_report(
    project_id: int,
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    analysis = db.query(DrawingAnalysis).filter(
        DrawingAnalysis.id == analysis_id,
        DrawingAnalysis.project_id == project_id
    ).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis record not found.")

    filepath, rel_path = report_service.generate_pdf_report(db, project_id, analysis_id)
    return FileResponse(
        path=str(filepath),
        filename=filepath.name,
        media_type="application/pdf"
    )
