from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict


class RequirementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    project_id: int
    requirement_code: str
    title: str
    requirement_type: str
    nominal_value: Optional[float] = None
    unit: str
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    tolerance_rule: str
    raw_text: str
    page_number: int
    section: Optional[str] = None
    source_bbox_json: Optional[Dict[str, Any]] = None
    confidence: float
    created_at: datetime


class RequirementCreate(BaseModel):
    requirement_code: str
    title: str
    requirement_type: str = "dimension_limit"
    nominal_value: Optional[float] = None
    unit: str = "mm"
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    tolerance_rule: str = "interval_containment"
    raw_text: str
    page_number: int = 1
    section: Optional[str] = None
