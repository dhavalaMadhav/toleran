import shutil
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, User, Project, Document, ProcessingJob, DrawingAnalysis, ExtractedAnnotation, ComplianceFinding, SpecificationRequirement
from app.agents.workflow import workflow_orchestrator
from app.services.storage_service import storage_service
from app.services.specification_service import specification_service
from app.services.report_service import report_service
from app.services.copilot_service import copilot_service


@pytest.fixture(scope="module")
def test_db():
    # In-memory test SQLite DB
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()

    user = User(
        email="test_engineer@internal.test",
        full_name="Test QA Engineer",
        hashed_password="hash",
        role="engineer"
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    project = Project(
        name="Integration Test Flange",
        part_number="AERO-SH-7740",
        revision="Rev B",
        created_by_id=user.id
    )
    session.add(project)
    session.commit()
    session.refresh(project)

    yield session
    session.close()


def test_end_to_end_pipeline(test_db):
    project = test_db.query(Project).first()
    assert project is not None

    fixtures_dir = Path("tests/fixtures")
    drawing_fixture = fixtures_dir / "synthetic_drawing.pdf"
    spec_fixture = fixtures_dir / "technical_specification.pdf"
    assert drawing_fixture.exists(), "Synthetic drawing fixture must exist"
    assert spec_fixture.exists(), "Technical specification fixture must exist"

    # 1. Ingest Specification
    spec_doc = Document(
        project_id=project.id,
        filename="technical_specification.pdf",
        original_filename="technical_specification.pdf",
        file_type="specification",
        mime_type="application/pdf",
        file_size_bytes=spec_fixture.stat().st_size,
        sha256_hash="spec_hash_123",
        storage_path=str(spec_fixture)
    )
    test_db.add(spec_doc)
    test_db.commit()
    test_db.refresh(spec_doc)

    reqs = specification_service.parse_specification_document(spec_fixture)
    assert len(reqs) >= 2, f"Expected at least 2 extracted requirements, got {len(reqs)}"
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
            page_number=r.page_number
        )
        test_db.add(req_obj)
    test_db.commit()

    # 2. Ingest Drawing Document
    drawing_doc = Document(
        project_id=project.id,
        filename="synthetic_drawing.pdf",
        original_filename="synthetic_drawing.pdf",
        file_type="drawing",
        mime_type="application/pdf",
        file_size_bytes=drawing_fixture.stat().st_size,
        sha256_hash="dwg_hash_456",
        storage_path=str(drawing_fixture)
    )
    test_db.add(drawing_doc)
    test_db.commit()
    test_db.refresh(drawing_doc)

    # 3. Create Processing Job
    job = ProcessingJob(
        document_id=drawing_doc.id,
        project_id=project.id,
        status="queued"
    )
    test_db.add(job)
    test_db.commit()
    test_db.refresh(job)

    # 4. Execute Full Pipeline via Workflow Orchestrator
    state = workflow_orchestrator.run_pipeline(test_db, job.id)
    assert state.status in ("completed", "needs_review")

    # 5. Verify Persisted Analysis Records
    analysis = test_db.query(DrawingAnalysis).filter(
        DrawingAnalysis.document_id == drawing_doc.id
    ).first()
    assert analysis is not None
    assert len(analysis.pages) >= 1

    annotations = test_db.query(ExtractedAnnotation).filter(
        ExtractedAnnotation.analysis_id == analysis.id
    ).all()
    assert len(annotations) > 0, "Pipeline must extract normalized annotations"

    # Find the diameter annotation
    diam_ann = next((a for a in annotations if a.dimension_type == "diameter"), None)
    assert diam_ann is not None, "Pipeline must detect diameter dimension"
    assert diam_ann.nominal_value == 20.0
    assert diam_ann.min_val == 19.9
    assert diam_ann.max_val == 20.1

    # 6. Verify Deterministic Compliance Findings
    findings = test_db.query(ComplianceFinding).filter(
        ComplianceFinding.analysis_id == analysis.id
    ).all()
    assert len(findings) > 0, "Compliance engine must produce findings against specifications"

    # Check that tolerance discrepancy was correctly flagged (19.9..20.1 exceeds spec 19.95..20.05)
    flagged_failure = next((f for f in findings if f.outcome == "fail"), None)
    assert flagged_failure is not None, "Compliance engine must flag tolerance interval overflow as FAIL"

    # 7. Verify Report Generation
    csv_report = report_service.generate_csv_report(test_db, project.id, analysis.id)
    assert "Annotation ID" in csv_report
    assert "20" in csv_report

    pdf_file, _ = report_service.generate_pdf_report(test_db, project.id, analysis.id)
    assert pdf_file.exists()
    assert pdf_file.stat().st_size > 1000

    # 8. Verify Grounded Engineering Copilot
    chat_resp = copilot_service.process_query(
        db=test_db,
        project_id=project.id,
        query="Why was this tolerance flagged?"
    )
    assert chat_resp.content is not None
    assert len(chat_resp.citations) > 0, "Copilot must return grounded citations"
    assert any("Finding" in c.identifier for c in chat_resp.citations)
