import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.agents.state import PipelineState
from app.config import settings
from app.core.logging import logger
from app.database.models import (
    Document, ProcessingJob, DrawingAnalysis, DrawingPage,
    ExtractedAnnotation, GeometricFeature, AnnotationFeatureAssociation,
    ComplianceFinding, SpecificationRequirement
)
from app.schemas.annotation import BoundingBox, NormalizedDimension
from app.services.pdf_service import pdf_service
from app.services.cad_service import cad_service
from app.services.ocr_service import ocr_service
from app.services.drawing_geometry_service import drawing_geometry_service
from app.services.dimension_parser import dimension_parser
from app.services.feature_association_service import feature_association_service
from app.services.retrieval_service import retrieval_service
from app.services.compliance_engine import compliance_engine
from app.services.evidence_service import evidence_service
from app.services.vlm_service import vlm_service
from app.services.preprocessing_service import preprocessing_service


class WorkflowOrchestrator:
    """
    Controlled multi-stage engineering pipeline orchestrator.
    Handles document ingestion, vector/raster extraction, OCR, dimension parsing,
    geometric association, compliance checking, and persistence.
    """

    def run_pipeline(self, db: Session, job_id: int) -> PipelineState:
        start_time = time.time()
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            raise ValueError(f"ProcessingJob #{job_id} not found.")

        doc = db.query(Document).filter(Document.id == job.document_id).first()
        if not doc:
            job.status = "failed"
            job.error_message = "Associated document record missing."
            db.commit()
            raise ValueError(f"Document #{job.document_id} not found.")

        state = PipelineState(
            job_id=job.id,
            project_id=job.project_id,
            document_id=doc.id,
            file_path=doc.storage_path,
            file_type=doc.file_type,
            status="processing",
            progress_pct=5
        )

        job.status = "processing"
        job.progress_pct = 5
        db.commit()

        try:
            # Stage 1: Document Validation & Classification
            self._stage_validate(state)
            job.stage = "inspection"
            job.progress_pct = 20
            db.commit()

            # Stage 2: Page Rendering & Vector Inspection
            self._stage_render_pages(state)
            job.stage = "ocr_and_geometry"
            job.progress_pct = 40
            db.commit()

            # Stage 3: OCR & Geometric Feature Extraction
            self._stage_ocr_and_geometry(state)
            job.stage = "dimension_normalization"
            job.progress_pct = 60
            db.commit()

            # Stage 4: Dimension Normalization & Ambiguity Detection
            self._stage_normalize_dimensions(state)
            job.stage = "feature_association"
            job.progress_pct = 75
            db.commit()

            # Stage 5: Feature Association
            self._stage_associate_features(state)
            job.stage = "compliance_evaluation"
            job.progress_pct = 85
            db.commit()

            # Stage 6: Compliance Validation against Specifications
            self._stage_compliance_check(db, state)
            job.stage = "persistence"
            job.progress_pct = 95
            db.commit()

            # Stage 7: Persist Canonical Results
            analysis = self._stage_persist_results(db, state)

            elapsed = round(time.time() - start_time, 2)
            job.execution_time_sec = elapsed
            job.progress_pct = 100
            job.status = "needs_review" if state.requires_human_review else "completed"
            state.status = job.status
            db.commit()

            logger.info(f"Pipeline finished for Job #{job.id} in {elapsed}s with status: {job.status}")
            return state

        except Exception as e:
            elapsed = round(time.time() - start_time, 2)
            logger.error(f"Pipeline failed for Job #{job.id}: {e}", exc_info=True)
            job.status = "failed"
            job.error_message = str(e)
            job.execution_time_sec = elapsed
            db.commit()
            state.status = "failed"
            state.error_message = str(e)
            return state

    def _stage_validate(self, state: PipelineState) -> None:
        path = Path(state.file_path)
        if not path.exists():
            raise FileNotFoundError(f"File at '{state.file_path}' does not exist on disk.")
        state.current_stage = "inspection"

    def _stage_render_pages(self, state: PipelineState) -> None:
        path = Path(state.file_path)
        ext = path.suffix.lower()

        if ext == ".pdf":
            info = pdf_service.inspect_document(path)
            state.page_count = info["page_count"]

            for page_idx in range(info["page_count"]):
                p_num = page_idx + 1
                rel_img, rw, rh, wpt, hpt = pdf_service.render_page_to_image(path, page_number=p_num)
                vector_elems = pdf_service.extract_vector_elements(path, page_number=p_num)
                native_blocks = pdf_service.extract_native_text_blocks(path, page_number=p_num)

                state.page_renders.append({
                    "page_number": p_num,
                    "render_image_path": rel_img,
                    "render_width_px": rw,
                    "render_height_px": rh,
                    "width_pt": wpt,
                    "height_pt": hpt,
                    "has_native_text": len(native_blocks) > 0,
                    "has_vectors": len(vector_elems) > 0
                })
                state.native_text_blocks.extend(native_blocks)

        elif ext in (".png", ".jpg", ".jpeg"):
            state.page_count = 1
            # Image is already its own render
            img = preprocessing_service.load_image(path)
            h, w = img.shape[:2]
            state.page_renders.append({
                "page_number": 1,
                "render_image_path": str(path.relative_to(Path(".")) if path.is_relative_to(Path(".")) else path),
                "render_width_px": w,
                "render_height_px": h,
                "width_pt": float(w),
                "height_pt": float(h),
                "has_native_text": False,
                "has_vectors": False
            })

        elif ext == ".dxf":
            state.page_count = 1
            cad_data = cad_service.parse_dxf(path)
            # Create a synthetic placeholder preview for DXF or raster preview
            state.page_renders.append({
                "page_number": 1,
                "render_image_path": str(path.relative_to(Path(".")) if path.is_relative_to(Path(".")) else path),
                "render_width_px": 800,
                "render_height_px": 600,
                "width_pt": 800.0,
                "height_pt": 600.0,
                "has_native_text": True,
                "has_vectors": True
            })

    def _stage_ocr_and_geometry(self, state: PipelineState) -> None:
        path = Path(state.file_path)
        ext = path.suffix.lower()

        if ext == ".dxf":
            cad_data = cad_service.parse_dxf(path)
            # Use CAD annotations as raw boxes
            for ann in cad_data["annotations"]:
                state.raw_ocr_boxes.append({
                    "text": ann["text"],
                    "confidence": 0.99,
                    "bbox": BoundingBox(x0=0.1, y0=0.1, x1=0.2, y1=0.15),
                    "page_number": 1,
                    "source": "cad_entity"
                })
            for ent in cad_data["entities"]:
                state.geometric_features.append({
                    "feature_type": ent["type"],
                    "center_x": 0.5,
                    "center_y": 0.5,
                    "radius": ent.get("radius"),
                    "bbox_x0": 0.4,
                    "bbox_y0": 0.4,
                    "bbox_x1": 0.6,
                    "bbox_y1": 0.6,
                    "evidence": f"CAD {ent['type']} entity handle {ent.get('handle')}"
                })
            return

        # For PDF / raster images: run RapidOCR and geometry detector on each rendered page
        for p_info in state.page_renders:
            p_img_path = p_info["render_image_path"]
            p_num = p_info["page_number"]

            ocr_results = ocr_service.extract_text_regions(p_img_path, page_number=p_num)
            state.raw_ocr_boxes.extend(ocr_results)

            geo_features = drawing_geometry_service.detect_features_from_image(p_img_path)
            for gf in geo_features:
                gf["page_number"] = p_num
            state.geometric_features.extend(geo_features)

    def _stage_normalize_dimensions(self, state: PipelineState) -> None:
        # Merge native text blocks and OCR boxes to avoid duplicate extractions
        seen_texts = set()
        candidates = []

        # First add native text blocks (if high precision)
        for nb in state.native_text_blocks:
            clean = nb["text"].strip()
            if clean and clean not in seen_texts:
                seen_texts.add(clean)
                candidates.append({
                    "text": clean,
                    "bbox": nb["bbox_norm"],
                    "confidence": 0.95,
                    "source": "native_pdf_text",
                    "page_number": nb["page_number"]
                })

        # Add OCR boxes
        for ob in state.raw_ocr_boxes:
            clean = ob["text"].strip()
            if clean and clean not in seen_texts:
                seen_texts.add(clean)
                candidates.append({
                    "text": clean,
                    "bbox": ob["bbox"],
                    "confidence": ob["confidence"],
                    "source": ob.get("source", "ocr"),
                    "page_number": ob["page_number"]
                })

        # Parse with DimensionParser
        for cand in candidates:
            parsed = dimension_parser.parse(
                raw_text=cand["text"],
                bbox=cand["bbox"],
                page_number=cand["page_number"],
                extraction_method=cand["source"],
                confidence=cand["confidence"]
            )

            # Filter out non-engineering strings (e.g. page headers or random text notes)
            # keep if it's a dimension, thread, angular, diameter, radius, or explicit tolerance
            if parsed.dimension_type != "general_note" or parsed.nominal_value is not None:
                state.normalized_annotations.append(parsed)
                if parsed.is_ambiguous or parsed.verification_status == "pending_review":
                    state.requires_human_review = True
                    state.review_reasons.append(f"Ambiguous dimension: '{parsed.original_text}'")

    def _stage_associate_features(self, state: PipelineState) -> None:
        associations = feature_association_service.associate_annotations_with_features(
            annotations=state.normalized_annotations,
            features=state.geometric_features
        )
        state.feature_associations = associations

        for assoc in associations:
            if assoc.get("is_ambiguous"):
                state.requires_human_review = True
                state.review_reasons.append(assoc.get("ambiguity_reason") or "Ambiguous geometric feature link")

    def _stage_compliance_check(self, db: Session, state: PipelineState) -> None:
        for ann in state.normalized_annotations:
            matched_reqs = retrieval_service.find_matching_requirements(
                db=db,
                project_id=state.project_id,
                dimension_type=ann.dimension_type,
                nominal_value=ann.nominal_value,
                unit=ann.unit
            )

            for req in matched_reqs:
                findings = compliance_engine.evaluate_annotation_against_requirement(ann, req)
                for f in findings:
                    f["annotation"] = ann
                    f["requirement_id"] = req.id
                    state.compliance_findings.append(f)
                    if f["outcome"] in ("fail", "needs_review"):
                        state.requires_human_review = True
                        state.review_reasons.append(f"Compliance finding [{f['outcome']}]: {f['explanation']}")

    def _stage_persist_results(self, db: Session, state: PipelineState) -> DrawingAnalysis:
        analysis = DrawingAnalysis(
            document_id=state.document_id,
            project_id=state.project_id,
            pipeline_version="1.0.0",
            vlm_used=settings.VLM_ENABLED,
            status="needs_review" if state.requires_human_review else "completed",
            summary_json={
                "page_count": state.page_count,
                "total_annotations": len(state.normalized_annotations),
                "total_features": len(state.geometric_features),
                "total_findings": len(state.compliance_findings),
                "requires_human_review": state.requires_human_review,
                "review_reasons": state.review_reasons
            }
        )
        db.add(analysis)
        db.flush()

        # Persist Pages
        page_id_map = {}
        for p_info in state.page_renders:
            p_obj = DrawingPage(
                analysis_id=analysis.id,
                document_id=state.document_id,
                page_number=p_info["page_number"],
                width_pt=p_info["width_pt"],
                height_pt=p_info["height_pt"],
                render_width_px=p_info["render_width_px"],
                render_height_px=p_info["render_height_px"],
                render_image_path=p_info["render_image_path"],
                text_layer_available=p_info["has_native_text"],
                vector_layer_available=p_info["has_vectors"]
            )
            db.add(p_obj)
            db.flush()
            page_id_map[p_info["page_number"]] = p_obj.id

        # Persist Geometric Features
        feature_id_map = {}
        for idx, feat in enumerate(state.geometric_features):
            p_num = feat.get("page_number", 1)
            gf_obj = GeometricFeature(
                analysis_id=analysis.id,
                page_id=page_id_map.get(p_num),
                feature_type=feat["feature_type"],
                center_x=feat.get("center_x"),
                center_y=feat.get("center_y"),
                radius=feat.get("radius"),
                bbox_x0=feat["bbox_x0"],
                bbox_y0=feat["bbox_y0"],
                bbox_x1=feat["bbox_x1"],
                bbox_y1=feat["bbox_y1"],
                properties_json={"evidence": feat.get("evidence")}
            )
            db.add(gf_obj)
            db.flush()
            feature_id_map[idx] = gf_obj.id

        # Persist Annotations & Generate Visual Crops
        annotation_id_map = {}
        for idx, ann in enumerate(state.normalized_annotations):
            p_id = page_id_map.get(ann.page_number)
            p_render = next((p for p in state.page_renders if p["page_number"] == ann.page_number), None)
            crop_path = None
            if p_render:
                crop_path = evidence_service.generate_annotation_crop(
                    render_image_path=p_render["render_image_path"],
                    bbox_x0=ann.bbox.x0,
                    bbox_y0=ann.bbox.y0,
                    bbox_x1=ann.bbox.x1,
                    bbox_y1=ann.bbox.y1
                )

            ann_obj = ExtractedAnnotation(
                analysis_id=analysis.id,
                page_id=p_id,
                page_number=ann.page_number,
                original_text=ann.original_text,
                dimension_type=ann.dimension_type,
                nominal_value=ann.nominal_value,
                unit=ann.unit,
                upper_deviation=ann.upper_deviation,
                lower_deviation=ann.lower_deviation,
                min_val=ann.min_val,
                max_val=ann.max_val,
                tolerance_type=ann.tolerance_type,
                bbox_x0=ann.bbox.x0,
                bbox_y0=ann.bbox.y0,
                bbox_x1=ann.bbox.x1,
                bbox_y1=ann.bbox.y1,
                crop_image_path=crop_path,
                extraction_method=ann.extraction_method,
                confidence=ann.confidence,
                is_ambiguous=ann.is_ambiguous,
                ambiguity_reason=ann.ambiguity_reason,
                verification_status=ann.verification_status
            )
            db.add(ann_obj)
            db.flush()
            annotation_id_map[idx] = ann_obj.id

        # Persist Associations
        for assoc in state.feature_associations:
            ann_idx = assoc["annotation_index"]
            feat_idx = assoc["feature_index"]
            if ann_idx in annotation_id_map and feat_idx in feature_id_map:
                assoc_obj = AnnotationFeatureAssociation(
                    annotation_id=annotation_id_map[ann_idx],
                    feature_id=feature_id_map[feat_idx],
                    association_method=assoc["association_method"],
                    confidence=assoc["confidence"],
                    is_ambiguous=assoc["is_ambiguous"],
                    ambiguity_notes=assoc["ambiguity_reason"],
                    review_status=assoc["review_status"]
                )
                db.add(assoc_obj)

        # Persist Compliance Findings
        for finding in state.compliance_findings:
            ann_ref = finding.get("annotation")
            matched_ann_id = None
            if ann_ref and hasattr(ann_ref, "original_text"):
                # Find matching persisted annotation
                for ann_i, ann_model_id in annotation_id_map.items():
                    if state.normalized_annotations[ann_i].original_text == ann_ref.original_text:
                        matched_ann_id = ann_model_id
                        break

            finding_obj = ComplianceFinding(
                analysis_id=analysis.id,
                project_id=state.project_id,
                annotation_id=matched_ann_id,
                requirement_id=finding.get("requirement_id"),
                rule_identifier=finding["rule_identifier"],
                finding_type=finding["finding_type"],
                severity=finding["severity"],
                outcome=finding["outcome"],
                expected_value=finding.get("expected_value"),
                observed_value=finding.get("observed_value"),
                deviation_value=finding.get("deviation_value"),
                rule_version=finding.get("rule_version", "1.0.0"),
                explanation=finding["explanation"],
                review_status="unresolved",
                evidence_json=finding.get("evidence")
            )
            db.add(finding_obj)

        db.commit()
        db.refresh(analysis)
        return analysis


workflow_orchestrator = WorkflowOrchestrator()
