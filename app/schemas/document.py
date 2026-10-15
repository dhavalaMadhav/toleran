from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    filename: str
    original_filename: str
    file_type: str
    mime_type: str
    file_size_bytes: int
    sha256_hash: str
    page_count: int
    created_at: datetime
    metadata_json: Optional[Dict[str, Any]] = None
    latest_analysis_id: Optional[int] = None
    latest_analysis_status: Optional[str] = None
