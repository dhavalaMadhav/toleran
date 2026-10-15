from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class Citation(BaseModel):
    source_type: str = Field(..., description="drawing_annotation, specification_requirement, compliance_finding, drawing_page")
    document_name: str
    page_number: int
    identifier: str  # Annotation #14, REQ-DIM-01, FINDING #3
    target_id: int
    excerpt_or_value: str
    bbox: Optional[Dict[str, float]] = None


class CopilotChatRequest(BaseModel):
    project_id: int
    message: str = Field(..., min_length=1)
    conversation_id: Optional[int] = None


class CopilotChatResponse(BaseModel):
    conversation_id: int
    message_id: int
    content: str
    citations: List[Citation] = Field(default_factory=list)
    tools_called: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
