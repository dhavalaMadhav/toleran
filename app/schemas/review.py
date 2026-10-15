from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class ReviewActionRequest(BaseModel):
    decision: str = Field(..., description="approved, rejected, modified, waived")
    notes: Optional[str] = None
    override_values: Optional[Dict[str, Any]] = None


class ReviewDecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    target_type: str
    target_id: int
    decision: str
    reviewer_name: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
