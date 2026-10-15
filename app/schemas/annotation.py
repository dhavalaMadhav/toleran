from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class BoundingBox(BaseModel):
    x0: float = Field(..., ge=0.0, le=1.0, description="Normalized left coordinate (0.0 to 1.0)")
    y0: float = Field(..., ge=0.0, le=1.0, description="Normalized top coordinate (0.0 to 1.0)")
    x1: float = Field(..., ge=0.0, le=1.0, description="Normalized right coordinate (0.0 to 1.0)")
    y1: float = Field(..., ge=0.0, le=1.0, description="Normalized bottom coordinate (0.0 to 1.0)")


class NormalizedDimension(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    original_text: str
    dimension_type: str = Field(default="linear", description="linear, diameter, radius, angular, thread, datum, general_note")
    nominal_value: Optional[float] = None
    unit: str = "mm"
    upper_deviation: Optional[float] = 0.0
    lower_deviation: Optional[float] = 0.0
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    tolerance_type: str = Field(default="bilateral", description="bilateral, asymmetric, limit, basic, unspecified")
    page_number: int = 1
    bbox: BoundingBox
    extraction_method: str = "ocr"  # native_pdf_text, ocr, vlm, cad_entity
    confidence: float = 0.0
    is_ambiguous: bool = False
    ambiguity_reason: Optional[str] = None
    verification_status: str = "pending_review"  # auto_accepted, pending_review, approved, corrected, rejected


class AnnotationCorrectionRequest(BaseModel):
    dimension_type: Optional[str] = None
    nominal_value: Optional[float] = None
    unit: Optional[str] = None
    upper_deviation: Optional[float] = None
    lower_deviation: Optional[float] = None
    tolerance_type: Optional[str] = None
    verification_status: Optional[str] = None
    notes: Optional[str] = None


class ExtractedAnnotationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    analysis_id: int
    page_id: Optional[int] = None
    page_number: int
    original_text: str
    dimension_type: str
    nominal_value: Optional[float] = None
    unit: str
    upper_deviation: Optional[float] = None
    lower_deviation: Optional[float] = None
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    tolerance_type: str
    bbox_x0: float
    bbox_y0: float
    bbox_x1: float
    bbox_y1: float
    crop_image_path: Optional[str] = None
    extraction_method: str
    confidence: float
    is_ambiguous: bool
    ambiguity_reason: Optional[str] = None
    verification_status: str
    reviewed_by_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    reviewer_notes: Optional[str] = None
    created_at: datetime
