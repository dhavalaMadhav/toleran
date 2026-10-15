from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.core.exceptions import AppError
from app.core.logging import logger
from app.database import Base, engine, SessionLocal, User, Project
from app.core.security import hash_password
from app.api.routes import (
    pages, projects, documents, analysis,
    annotations, specifications, compliance,
    copilot, review, reports, health
)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        description="Engineering Drawing Intelligence & Design Compliance Copilot",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc"
    )

    # Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Ensure storage and static directories exist
    settings.ensure_directories()
    static_dir = Path("app/static")
    static_dir.mkdir(parents=True, exist_ok=True)
    (static_dir / "css").mkdir(parents=True, exist_ok=True)
    (static_dir / "js").mkdir(parents=True, exist_ok=True)

    # Mount static assets
    app.mount("/static/data/storage", StaticFiles(directory=str(settings.STORAGE_DIR)), name="storage_files")
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Include REST API v1
    from fastapi import APIRouter
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(health.router)
    api_v1.include_router(projects.router)
    api_v1.include_router(documents.router)
    api_v1.include_router(analysis.router)
    api_v1.include_router(annotations.router)
    api_v1.include_router(specifications.router)
    api_v1.include_router(compliance.router)
    api_v1.include_router(copilot.router)
    api_v1.include_router(review.router)
    api_v1.include_router(reports.router)

    app.include_router(api_v1)
    app.include_router(pages.router)

    # Domain Exception Handler
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.message}
        )

    # Database Initialization on Startup
    @app.on_event("startup")
    def on_startup():
        logger.info("Initializing relational database schema...")
        Base.metadata.create_all(bind=engine)

        db = SessionLocal()
        try:
            # Seed default admin engineer if absent
            user = db.query(User).filter(User.email == "engineer@cadcopilot.internal").first()
            if not user:
                user = User(
                    email="engineer@cadcopilot.internal",
                    full_name="Lead Engineering Reviewer",
                    hashed_password=hash_password("admin123"),
                    role="engineer"
                )
                db.add(user)
                db.commit()
                db.refresh(user)

            # Seed initial demo project if database has 0 projects
            proj_count = db.query(Project).count()
            if proj_count == 0:
                demo_proj = Project(
                    name="Flange Shaft Assembly 2026",
                    description="High-precision aerospace transmission shaft with critical bearing journals and bolt flanges.",
                    part_number="AERO-SH-7740",
                    revision="Rev B",
                    status="active",
                    created_by_id=user.id
                )
                db.add(demo_proj)
                db.commit()
                logger.info(f"Initialized demonstration project #{demo_proj.id}: {demo_proj.name}")
        finally:
            db.close()

    return app


app = create_app()
