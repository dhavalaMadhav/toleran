import shutil
import sys
from pathlib import Path

# Ensure workspace root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal, Base, engine, User, Project, Document, ProcessingJob, DrawingAnalysis
from app.core.security import hash_password
from app.agents.workflow import workflow_orchestrator
from app.services.storage_service import storage_service
from app.services.specification_service import specification_service
from app.database.models import SpecificationRequirement


def seed_demo_data():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Lead Engineer User
        user = db.query(User).filter(User.email == "engineer@cadcopilot.internal").first()
        if not user:
            user = User(
                email="engineer@cadcopilot.internal",
                full_name="Lead Systems Engineer",
                hashed_password=hash_password("admin123"),
                role="engineer"
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # 2. Project
        project = db.query(Project).filter(Project.part_number == "AERO-SH-7740").first()
        if not project:
            project = Project(
                name="Flange Shaft Assembly 2026",
                description="High-precision aerospace transmission shaft with critical bearing journals and bolt flanges.",
                part_number="AERO-SH-7740",
                revision="Rev B",
                status="active",
                created_by_id=user.id
            )
            db.add(project)
            db.commit()
            db.refresh(project)

        fixtures_dir = Path("tests/fixtures")
        dwg_src = fixtures_dir / "synthetic_drawing.pdf"
        spec_src = fixtures_dir / "technical_specification.pdf"

        # Copy fixtures into data/storage
        dwg_target = Path("data/storage/drawings") / "flange_shaft_drawing_revB.pdf"
        spec_target = Path("data/storage/specs") / "aerospace_spec_aero_7740.pdf"
        dwg_target.parent.mkdir(parents=True, exist_ok=True)
        spec_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dwg_src, dwg_target)
        shutil.copy2(spec_src, spec_target)

        # 3. Specification Document & Requirements
        spec_doc = db.query(Document).filter(
            Document.project_id == project.id,
            Document.file_type == "specification"
        ).first()

        if not spec_doc:
            spec_hash = storage_service.compute_sha256(spec_target)
            spec_doc = Document(
                project_id=project.id,
                filename=spec_target.name,
                original_filename="aerospace_spec_aero_7740.pdf",
                file_type="specification",
                mime_type="application/pdf",
                file_size_bytes=spec_target.stat().st_size,
                sha256_hash=spec_hash,
                storage_path=str(spec_target)
            )
            db.add(spec_doc)
            db.commit()
            db.refresh(spec_doc)

            reqs = specification_service.parse_specification_document(spec_target)
            for r in reqs:
                req_obj = SpecificationRequirement(
                    document_id=spec_doc.id,
                    project_id=project.id,
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

        # 4. Drawing Document
        dwg_doc = db.query(Document).filter(
            Document.project_id == project.id,
            Document.file_type == "drawing"
        ).first()

        if not dwg_doc:
            dwg_hash = storage_service.compute_sha256(dwg_target)
            dwg_doc = Document(
                project_id=project.id,
                filename=dwg_target.name,
                original_filename="flange_shaft_drawing_revB.pdf",
                file_type="drawing",
                mime_type="application/pdf",
                file_size_bytes=dwg_target.stat().st_size,
                sha256_hash=dwg_hash,
                storage_path=str(dwg_target),
                page_count=1
            )
            db.add(dwg_doc)
            db.commit()
            db.refresh(dwg_doc)

        # 5. Execute Analysis Pipeline if no analysis exists
        analysis = db.query(DrawingAnalysis).filter(DrawingAnalysis.document_id == dwg_doc.id).first()
        if not analysis:
            job = ProcessingJob(
                document_id=dwg_doc.id,
                project_id=project.id,
                status="queued"
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            workflow_orchestrator.run_pipeline(db, job.id)
            print("Successfully processed demonstration drawing analysis!")

        print("Demonstration data seeded successfully.")

    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_data()
