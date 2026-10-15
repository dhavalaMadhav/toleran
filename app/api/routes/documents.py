from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.dependencies import get_db, get_current_user
from app.database.models import Document, Project, ProcessingJob, DrawingAnalysis, User
from app.schemas.document import DocumentResponse
from app.schemas.common import APIResponse
from app.services.storage_service import storage_service
from app.services.specification_service import specification_service
from app.database.models import SpecificationRequirement

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=APIResponse[DocumentResponse], status_code=status.HTTP_201_CREATED)
def upload_document(
    project_id: int = Form(...),
    file_type: str = Form("drawing"),  # drawing, specification, cad
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    original_filename = file.filename or "uploaded_file"
    ext = Path(original_filename).suffix.lower()

    if file_type == "drawing" and ext not in (".pdf", ".png", ".jpg", ".jpeg", ".dxf"):
        raise HTTPException(status_code=415, detail=f"Unsupported drawing format '{ext}'. Allowed: PDF, PNG, JPG, JPEG, DXF.")
    elif file_type == "specification" and ext not in (".pdf", ".txt", ".md"):
        raise HTTPException(status_code=415, detail=f"Unsupported specification format '{ext}'. Allowed: PDF, TXT, MD.")

    subfolder = "specs" if file_type == "specification" else "drawings"
    safe_name, rel_path, file_size, sha256 = storage_service.save_upload_file(file, subfolder=subfolder)

    # Check for identical upload hash within the project
    existing = db.query(Document).filter(
        Document.project_id == project_id,
        Document.sha256_hash == sha256
    ).first()

    if existing:
        return APIResponse(
            message="Identical document already uploaded in this project (deduplicated by SHA256)",
            data=DocumentResponse.model_validate(existing)
        )

    # Detect initial page count
    page_count = 1
    if ext == ".pdf":
        try:
            import fitz
            doc_fitz = fitz.open(str(storage_service.get_absolute_path(rel_path)))
            page_count = len(doc_fitz)
            doc_fitz.close()
        except Exception:
            page_count = 1

    doc = Document(
        project_id=project_id,
        filename=safe_name,
        original_filename=original_filename,
        file_type=file_type,
        mime_type=file.content_type or "application/octet-stream",
        file_size_bytes=file_size,
        sha256_hash=sha256,
        storage_path=rel_path,
        page_count=page_count,
        metadata_json={"extension": ext}
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # If it is a specification, parse requirements immediately into the database
    if file_type == "specification":
        try:
            reqs = specification_service.parse_specification_document(storage_service.get_absolute_path(rel_path))
            for r in reqs:
                req_obj = SpecificationRequirement(
                    document_id=doc.id,
                    project_id=project_id,
                    requirement_code=r.requirement_code,
                    title=r.title,
                    requirement_type=r.requirement_type,
                    nominal_value=r.nominal_value,
                    unit=r.unit,
                    min_val=r.min_val,
                    max_val=r.max_val,
                    tolerance_rule=r.tolerance_rule,
                    raw_text=r.raw_text,
                    page_number=r.page_number,
                    section=r.section,
                    confidence=1.0
                )
                db.add(req_obj)
            db.commit()
        except Exception as e:
            pass

    return APIResponse(
        message="Document uploaded successfully",
        data=DocumentResponse.model_validate(doc)
    )


@router.get("/project/{project_id}", response_model=APIResponse[List[DocumentResponse]])
def list_project_documents(
    project_id: int,
    file_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    q = db.query(Document).filter(Document.project_id == project_id)
    if file_type:
        q = q.filter(Document.file_type == file_type)
    docs = q.order_by(Document.created_at.desc()).all()

    results = []
    for d in docs:
        latest_analysis = db.query(DrawingAnalysis).filter(DrawingAnalysis.document_id == d.id).order_by(DrawingAnalysis.created_at.desc()).first()
        results.append(DocumentResponse(
            id=d.id,
            project_id=d.project_id,
            filename=d.filename,
            original_filename=d.original_filename,
            file_type=d.file_type,
            mime_type=d.mime_type,
            file_size_bytes=d.file_size_bytes,
            sha256_hash=d.sha256_hash,
            page_count=d.page_count,
            created_at=d.created_at,
            metadata_json=d.metadata_json,
            latest_analysis_id=latest_analysis.id if latest_analysis else None,
            latest_analysis_status=latest_analysis.status if latest_analysis else None
        ))

    return APIResponse(data=results)


@router.get("/raw/{document_id}")
def download_raw_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    filepath = storage_service.get_absolute_path(doc.storage_path)
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found on storage disk.")

    return FileResponse(
        path=str(filepath),
        filename=doc.original_filename,
        media_type=doc.mime_type
    )
