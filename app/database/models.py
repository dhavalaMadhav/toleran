from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String, Integer, Float, Boolean, Text, ForeignKey, JSON, Index, DateTime
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="engineer", nullable=False)  # admin, engineer, reviewer
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    projects: Mapped[List["Project"]] = relationship("Project", back_populates="creator")
    reviews: Mapped[List["ReviewDecision"]] = relationship("ReviewDecision", back_populates="reviewer")


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    part_number: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    revision: Mapped[Optional[str]] = mapped_column(String(50), default="Rev A", nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)  # active, archived
    created_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    creator: Mapped[Optional["User"]] = relationship("User", back_populates="projects")
    documents: Mapped[List["Document"]] = relationship("Document", back_populates="project", cascade="all, delete-orphan")
    analyses: Mapped[List["DrawingAnalysis"]] = relationship("DrawingAnalysis", back_populates="project", cascade="all, delete-orphan")
    findings: Mapped[List["ComplianceFinding"]] = relationship("ComplianceFinding", back_populates="project", cascade="all, delete-orphan")
    conversations: Mapped[List["CopilotConversation"]] = relationship("CopilotConversation", back_populates="project", cascade="all, delete-orphan")


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)  # drawing, specification, cad
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)

    project: Mapped["Project"] = relationship("Project", back_populates="documents")
    analyses: Mapped[List["DrawingAnalysis"]] = relationship("DrawingAnalysis", back_populates="document", cascade="all, delete-orphan")
    requirements: Mapped[List["SpecificationRequirement"]] = relationship("SpecificationRequirement", back_populates="document", cascade="all, delete-orphan")
    jobs: Mapped[List["ProcessingJob"]] = relationship("ProcessingJob", back_populates="document", cascade="all, delete-orphan")


class ProcessingJob(Base, TimestampMixin):
    __tablename__ = "processing_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(100), default="ingestion", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="queued", index=True, nullable=False)  # queued, processing, needs_review, completed, failed
    progress_pct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_time_sec: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    retries: Mapped[int] = mapped_column(Integer, default=0)

    document: Mapped["Document"] = relationship("Document", back_populates="jobs")


class DrawingAnalysis(Base, TimestampMixin):
    __tablename__ = "drawing_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    pipeline_version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)
    vlm_used: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(50), default="completed", nullable=False)  # completed, needs_review, failed
    summary_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)

    project: Mapped["Project"] = relationship("Project", back_populates="analyses")
    document: Mapped["Document"] = relationship("Document", back_populates="analyses")
    pages: Mapped[List["DrawingPage"]] = relationship("DrawingPage", back_populates="analysis", cascade="all, delete-orphan")
    annotations: Mapped[List["ExtractedAnnotation"]] = relationship("ExtractedAnnotation", back_populates="analysis", cascade="all, delete-orphan")
    features: Mapped[List["GeometricFeature"]] = relationship("GeometricFeature", back_populates="analysis", cascade="all, delete-orphan")
    findings: Mapped[List["ComplianceFinding"]] = relationship("ComplianceFinding", back_populates="analysis", cascade="all, delete-orphan")


class DrawingPage(Base, TimestampMixin):
    __tablename__ = "drawing_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(Integer, ForeignKey("drawing_analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    width_pt: Mapped[float] = mapped_column(Float, default=0.0)
    height_pt: Mapped[float] = mapped_column(Float, default=0.0)
    render_width_px: Mapped[int] = mapped_column(Integer, default=0)
    render_height_px: Mapped[int] = mapped_column(Integer, default=0)
    render_image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    text_layer_available: Mapped[bool] = mapped_column(Boolean, default=False)
    vector_layer_available: Mapped[bool] = mapped_column(Boolean, default=False)

    analysis: Mapped["DrawingAnalysis"] = relationship("DrawingAnalysis", back_populates="pages")
    annotations: Mapped[List["ExtractedAnnotation"]] = relationship("ExtractedAnnotation", back_populates="page", cascade="all, delete-orphan")


class ExtractedAnnotation(Base, TimestampMixin):
    __tablename__ = "extracted_annotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(Integer, ForeignKey("drawing_analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    page_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("drawing_pages.id", ondelete="CASCADE"), nullable=True)
    page_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    # Textual callout
    original_text: Mapped[str] = mapped_column(String(255), nullable=False)
    dimension_type: Mapped[str] = mapped_column(String(50), default="linear", index=True, nullable=False)  # linear, diameter, radius, angular, thread, datum, general_note
    
    # Normalized numerical values
    nominal_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(20), default="mm", nullable=False)
    upper_deviation: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    lower_deviation: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    min_val: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_val: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tolerance_type: Mapped[str] = mapped_column(String(50), default="bilateral", nullable=False)  # bilateral, asymmetric, limit, basic, unspecified
    
    # Geometry and evidence coordinates (normalized 0.0 to 1.0 bounding box relative to page width/height)
    bbox_x0: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y0: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_x1: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y1: Mapped[float] = mapped_column(Float, nullable=False)
    raw_bbox_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)
    crop_image_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Extraction provenance
    extraction_method: Mapped[str] = mapped_column(String(50), default="ocr", nullable=False)  # native_pdf_text, ocr, vlm, cad_entity
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_ambiguous: Mapped[bool] = mapped_column(Boolean, default=False)
    ambiguity_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Verification workflow
    verification_status: Mapped[str] = mapped_column(String(50), default="pending_review", index=True, nullable=False)  # auto_accepted, pending_review, approved, corrected, rejected
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    corrected_values_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)

    analysis: Mapped["DrawingAnalysis"] = relationship("DrawingAnalysis", back_populates="annotations")
    page: Mapped[Optional["DrawingPage"]] = relationship("DrawingPage", back_populates="annotations")
    associations: Mapped[List["AnnotationFeatureAssociation"]] = relationship("AnnotationFeatureAssociation", back_populates="annotation", cascade="all, delete-orphan")
    findings: Mapped[List["ComplianceFinding"]] = relationship("ComplianceFinding", back_populates="annotation", cascade="all, delete-orphan")


class GeometricFeature(Base, TimestampMixin):
    __tablename__ = "geometric_features"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(Integer, ForeignKey("drawing_analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    page_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("drawing_pages.id", ondelete="CASCADE"), nullable=True)
    feature_type: Mapped[str] = mapped_column(String(50), nullable=False)  # circle, arc, line, slot, boundary, cad_entity
    center_x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    center_y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    radius: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_x0: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y0: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_x1: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y1: Mapped[float] = mapped_column(Float, nullable=False)
    entity_layer: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    properties_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)

    analysis: Mapped["DrawingAnalysis"] = relationship("DrawingAnalysis", back_populates="features")
    associations: Mapped[List["AnnotationFeatureAssociation"]] = relationship("AnnotationFeatureAssociation", back_populates="feature", cascade="all, delete-orphan")


class AnnotationFeatureAssociation(Base, TimestampMixin):
    __tablename__ = "annotation_feature_associations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    annotation_id: Mapped[int] = mapped_column(Integer, ForeignKey("extracted_annotations.id", ondelete="CASCADE"), nullable=False, index=True)
    feature_id: Mapped[int] = mapped_column(Integer, ForeignKey("geometric_features.id", ondelete="CASCADE"), nullable=False, index=True)
    association_method: Mapped[str] = mapped_column(String(100), default="proximity_and_type", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    is_ambiguous: Mapped[bool] = mapped_column(Boolean, default=False)
    ambiguity_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)

    annotation: Mapped["ExtractedAnnotation"] = relationship("ExtractedAnnotation", back_populates="associations")
    feature: Mapped["GeometricFeature"] = relationship("GeometricFeature", back_populates="associations")


class SpecificationRequirement(Base, TimestampMixin):
    __tablename__ = "specification_requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    requirement_code: Mapped[str] = mapped_column(String(100), index=True, nullable=False)  # e.g., REQ-DIM-01
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    requirement_type: Mapped[str] = mapped_column(String(50), default="dimension_limit", nullable=False)  # dimension_limit, surface_finish, material, thread, general_tolerance
    
    # Structured constraints
    nominal_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(20), default="mm", nullable=False)
    min_val: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_val: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tolerance_rule: Mapped[str] = mapped_column(String(50), default="interval_containment", nullable=False)
    
    # Grounded evidence
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    section: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_bbox_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)

    document: Mapped["Document"] = relationship("Document", back_populates="requirements")
    findings: Mapped[List["ComplianceFinding"]] = relationship("ComplianceFinding", back_populates="requirement", cascade="all, delete-orphan")


class ComplianceFinding(Base, TimestampMixin):
    __tablename__ = "compliance_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(Integer, ForeignKey("drawing_analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    annotation_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("extracted_annotations.id", ondelete="CASCADE"), nullable=True, index=True)
    requirement_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("specification_requirements.id", ondelete="CASCADE"), nullable=True, index=True)
    
    rule_identifier: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., RULE_TOLERANCE_INTERVAL_CONTAINMENT
    finding_type: Mapped[str] = mapped_column(String(100), nullable=False)  # dimension_deviation, unit_mismatch, missing_tolerance, thread_mismatch, etc.
    severity: Mapped[str] = mapped_column(String(50), default="warning", index=True, nullable=False)  # error, warning, info
    outcome: Mapped[str] = mapped_column(String(50), default="pass", index=True, nullable=False)  # pass, fail, needs_review, not_evaluable
    
    expected_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    observed_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    deviation_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rule_version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    
    review_status: Mapped[str] = mapped_column(String(50), default="unresolved", index=True, nullable=False)  # unresolved, approved_deviation, waived, remediated
    evidence_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    analysis: Mapped["DrawingAnalysis"] = relationship("DrawingAnalysis", back_populates="findings")
    project: Mapped["Project"] = relationship("Project", back_populates="findings")
    annotation: Mapped[Optional["ExtractedAnnotation"]] = relationship("ExtractedAnnotation", back_populates="findings")
    requirement: Mapped[Optional["SpecificationRequirement"]] = relationship("SpecificationRequirement", back_populates="findings")


class ReviewDecision(Base, TimestampMixin):
    __tablename__ = "review_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)  # annotation, association, finding
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[str] = mapped_column(String(50), nullable=False)  # approved, rejected, modified, waived
    previous_state_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)
    new_state_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)
    reviewer_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    reviewer: Mapped["User"] = relationship("User", back_populates="reviews")


class CopilotConversation(Base, TimestampMixin):
    __tablename__ = "copilot_conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), default="Engineering Q&A", nullable=False)

    project: Mapped["Project"] = relationship("Project", back_populates="conversations")
    messages: Mapped[List["CopilotMessage"]] = relationship("CopilotMessage", back_populates="conversation", cascade="all, delete-orphan")


class CopilotMessage(Base, TimestampMixin):
    __tablename__ = "copilot_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(Integer, ForeignKey("copilot_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations_json: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, default=list)
    tools_called_json: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, default=list)

    conversation: Mapped["CopilotConversation"] = relationship("CopilotConversation", back_populates="messages")


class AuditEvent(Base, TimestampMixin):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    details_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)
    ip_address: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
