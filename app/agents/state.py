from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from app.schemas.annotation import NormalizedDimension, BoundingBox


class PipelineState(BaseModel):
    """Execution state representing the end-to-end document intelligence pipeline."""
    job_id: int
    project_id: int
    document_id: int
    file_path: str
    file_type: str  # drawing, specification, cad
    current_stage: str = "validation"
    status: str = "queued"
    progress_pct: int = 0
    error_message: Optional[str] = None
    retries: int = 0

    # Intermediate processing artifacts
    page_count: int = 1
    page_renders: List[Dict[str, Any]] = Field(default_factory=list)
    raw_ocr_boxes: List[Dict[str, Any]] = Field(default_factory=list)
    native_text_blocks: List[Dict[str, Any]] = Field(default_factory=list)
    geometric_features: List[Dict[str, Any]] = Field(default_factory=list)

    # Normalized records
    normalized_annotations: List[NormalizedDimension] = Field(default_factory=list)
    feature_associations: List[Dict[str, Any]] = Field(default_factory=list)
    matched_requirements: List[Dict[str, Any]] = Field(default_factory=list)
    compliance_findings: List[Dict[str, Any]] = Field(default_factory=list)

    # Human review routing
    requires_human_review: bool = False
    review_reasons: List[str] = Field(default_factory=list)
