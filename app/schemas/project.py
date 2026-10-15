from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    part_number: Optional[str] = None
    revision: Optional[str] = "Rev A"


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    part_number: Optional[str] = None
    revision: Optional[str] = None
    status: Optional[str] = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    part_number: Optional[str] = None
    revision: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    drawing_count: Optional[int] = 0
    spec_count: Optional[int] = 0
    unresolved_findings_count: Optional[int] = 0
