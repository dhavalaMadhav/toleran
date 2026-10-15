from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict


class ComplianceFindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    analysis_id: int
    project_id: int
    annotation_id: Optional[int] = None
    requirement_id: Optional[int] = None
    rule_identifier: str
    finding_type: str
    severity: str  # error, warning, info
    outcome: str   # pass, fail, needs_review, not_evaluable
    expected_value: Optional[str] = None
    observed_value: Optional[str] = None
    deviation_value: Optional[str] = None
    rule_version: str
    explanation: str
    review_status: str  # unresolved, approved_deviation, waived, remediated
    evidence_json: Optional[Dict[str, Any]] = None
    annotation_text: Optional[str] = None
    requirement_code: Optional[str] = None
    created_at: datetime


class ComplianceSummaryResponse(BaseModel):
    total_findings: int
    passed: int
    failed: int
    needs_review: int
    not_evaluable: int
    critical_errors: int
    warnings: int
    findings: List[ComplianceFindingResponse]
