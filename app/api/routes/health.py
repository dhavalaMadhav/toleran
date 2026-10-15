from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.dependencies import get_db
from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    storage_ok = settings.STORAGE_DIR.exists() and settings.STORAGE_DIR.is_dir()

    return {
        "status": "healthy" if db_ok and storage_ok else "degraded",
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "database_connected": db_ok,
        "storage_writable": storage_ok,
        "ocr_engine": settings.OCR_ENGINE,
        "vlm_enabled": settings.VLM_ENABLED,
        "llm_provider": settings.LLM_PROVIDER
    }
