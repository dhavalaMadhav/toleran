import pytest
from app.schemas.annotation import NormalizedDimension, BoundingBox
from app.schemas.specification import RequirementCreate
from app.services.compliance_engine import compliance_engine


def test_compliance_engine_pass():
    ann = NormalizedDimension(
        original_text="20 +/-0.05 mm",
        dimension_type="diameter",
        nominal_value=20.0,
        unit="mm",
        min_val=19.95,
        max_val=20.05,
        bbox=BoundingBox(x0=0.1, y0=0.1, x1=0.2, y1=0.2),
        confidence=0.95
    )
    req = RequirementCreate(
        requirement_code="REQ-DIM-01",
        title="Shaft Journal Diameter",
        nominal_value=20.0,
        unit="mm",
        min_val=19.90,
        max_val=20.10,
        tolerance_rule="interval_containment",
        raw_text="Diameter shall be 20 +/-0.1 mm"
    )

    findings = compliance_engine.evaluate_annotation_against_requirement(ann, req)
    assert len(findings) > 0
    f = findings[0]
    assert f["outcome"] == "pass"
    assert f["severity"] == "info"


def test_compliance_engine_fail_interval_exceeded():
    ann = NormalizedDimension(
        original_text="20 +/-0.2 mm",
        dimension_type="diameter",
        nominal_value=20.0,
        unit="mm",
        min_val=19.80,
        max_val=20.20,
        bbox=BoundingBox(x0=0.1, y0=0.1, x1=0.2, y1=0.2),
        confidence=0.95
    )
    req = RequirementCreate(
        requirement_code="REQ-DIM-01",
        title="Shaft Journal Diameter",
        nominal_value=20.0,
        unit="mm",
        min_val=19.90,
        max_val=20.10,
        tolerance_rule="interval_containment",
        raw_text="Diameter shall be 20 +/-0.1 mm"
    )

    findings = compliance_engine.evaluate_annotation_against_requirement(ann, req)
    assert len(findings) > 0
    f = findings[0]
    assert f["outcome"] == "fail"
    assert f["severity"] == "error"


def test_compliance_engine_unit_mismatch():
    ann = NormalizedDimension(
        original_text="0.787 in",
        dimension_type="linear",
        nominal_value=0.787,
        unit="in",
        min_val=0.785,
        max_val=0.789,
        bbox=BoundingBox(x0=0.1, y0=0.1, x1=0.2, y1=0.2),
        confidence=0.95
    )
    req = RequirementCreate(
        requirement_code="REQ-DIM-01",
        title="Shaft Journal Diameter",
        nominal_value=20.0,
        unit="mm",
        min_val=19.90,
        max_val=20.10,
        raw_text="20 mm"
    )

    findings = compliance_engine.evaluate_annotation_against_requirement(ann, req)
    assert len(findings) > 0
    f = findings[0]
    assert f["outcome"] == "fail"
    assert f["finding_type"] == "unit_mismatch"
