from decimal import Decimal
from typing import List, Dict, Any, Optional
from app.schemas.annotation import NormalizedDimension
from app.schemas.specification import RequirementResponse
from app.services.tolerance_service import tolerance_service


class ComplianceEngine:
    """
    Deterministic engineering compliance calculation engine.
    Compares normalized drawing annotations and structured specification requirements.
    The LLM is NOT the authority for numeric tolerance decisions.
    """

    RULE_INTERVAL_CONTAINMENT = "RULE_INTERVAL_CONTAINMENT_V1"
    RULE_UNIT_COMPATIBILITY = "RULE_UNIT_COMPATIBILITY_V1"
    RULE_NOMINAL_ALIGNMENT = "RULE_NOMINAL_ALIGNMENT_V1"
    RULE_THREAD_SPECIFICATION = "RULE_THREAD_SPEC_V1"
    RULE_AMBIGUOUS_EXTRACTION = "RULE_AMBIGUOUS_EXTRACTION_V1"
    RULE_MISSING_REQUIREMENT = "RULE_MISSING_REQ_V1"

    def evaluate_annotation_against_requirement(
        self,
        annotation: NormalizedDimension,
        requirement: Any  # SpecificationRequirement model or schema
    ) -> List[Dict[str, Any]]:
        findings = []

        # 1. Unit compatibility check
        if annotation.unit.lower() != requirement.unit.lower():
            findings.append({
                "rule_identifier": self.RULE_UNIT_COMPATIBILITY,
                "finding_type": "unit_mismatch",
                "severity": "error",
                "outcome": "fail",
                "expected_value": requirement.unit,
                "observed_value": annotation.unit,
                "deviation_value": f"Unit mismatch: {annotation.unit} vs {requirement.unit}",
                "rule_version": "1.0.0",
                "explanation": (
                    f"Drawing annotation '{annotation.original_text}' uses unit '{annotation.unit}', "
                    f"which conflicts with technical specification requirement unit '{requirement.unit}'."
                ),
                "review_status": "unresolved",
                "evidence": {
                    "drawing_unit": annotation.unit,
                    "spec_unit": requirement.unit,
                    "drawing_text": annotation.original_text,
                    "requirement_code": requirement.requirement_code
                }
            })
            return findings

        # 2. Check if annotation is ambiguous or low confidence
        if annotation.is_ambiguous or annotation.confidence < 0.60:
            findings.append({
                "rule_identifier": self.RULE_AMBIGUOUS_EXTRACTION,
                "finding_type": "unverified_annotation",
                "severity": "warning",
                "outcome": "needs_review",
                "expected_value": f"Verified dimension with confidence >= 0.88",
                "observed_value": f"Extracted '{annotation.original_text}' (conf: {annotation.confidence:.2f})",
                "deviation_value": annotation.ambiguity_reason or "Low OCR/extraction confidence",
                "rule_version": "1.0.0",
                "explanation": (
                    f"Drawing callout '{annotation.original_text}' has low extraction certainty or ambiguous structure: "
                    f"{annotation.ambiguity_reason or 'Verification required before automated compliance certification'}."
                ),
                "review_status": "unresolved",
                "evidence": {
                    "original_text": annotation.original_text,
                    "confidence": annotation.confidence,
                    "ambiguity_reason": annotation.ambiguity_reason
                }
            })

        # 3. Thread specification comparison
        if requirement.requirement_type == "thread":
            ann_text_clean = annotation.original_text.replace(" ", "").upper()
            req_text_clean = requirement.title.replace(" ", "").upper()
            is_match = False
            if requirement.nominal_value and annotation.nominal_value:
                is_match = (requirement.nominal_value == annotation.nominal_value)

            if is_match:
                findings.append({
                    "rule_identifier": self.RULE_THREAD_SPECIFICATION,
                    "finding_type": "thread_match",
                    "severity": "info",
                    "outcome": "pass",
                    "expected_value": requirement.title,
                    "observed_value": annotation.original_text,
                    "deviation_value": "0.0",
                    "rule_version": "1.0.0",
                    "explanation": f"Drawing thread callout '{annotation.original_text}' conforms to requirement {requirement.requirement_code}.",
                    "review_status": "unresolved",
                    "evidence": {"drawing_text": annotation.original_text, "requirement_code": requirement.requirement_code}
                })
            else:
                findings.append({
                    "rule_identifier": self.RULE_THREAD_SPECIFICATION,
                    "finding_type": "thread_mismatch",
                    "severity": "error",
                    "outcome": "fail",
                    "expected_value": requirement.title,
                    "observed_value": annotation.original_text,
                    "deviation_value": "Thread parameter discrepancy",
                    "rule_version": "1.0.0",
                    "explanation": f"Drawing thread '{annotation.original_text}' does not match specified thread '{requirement.title}'.",
                    "review_status": "unresolved",
                    "evidence": {"drawing_text": annotation.original_text, "requirement_code": requirement.requirement_code}
                })
            return findings

        # 4. Dimensional tolerance interval containment
        if (
            annotation.min_val is not None and annotation.max_val is not None
            and requirement.min_val is not None and requirement.max_val is not None
        ):
            is_contained, details = tolerance_service.is_interval_contained(
                drawing_min=annotation.min_val,
                drawing_max=annotation.max_val,
                spec_min=requirement.min_val,
                spec_max=requirement.max_val
            )

            if is_contained:
                findings.append({
                    "rule_identifier": self.RULE_INTERVAL_CONTAINMENT,
                    "finding_type": "tolerance_interval_containment",
                    "severity": "info",
                    "outcome": "pass",
                    "expected_value": f"[{requirement.min_val}, {requirement.max_val}] {requirement.unit}",
                    "observed_value": f"[{annotation.min_val}, {annotation.max_val}] {annotation.unit}",
                    "deviation_value": "0.0 (Inside interval)",
                    "rule_version": "1.0.0",
                    "explanation": (
                        f"Compliant: Drawing permitted tolerance interval [{annotation.min_val}, {annotation.max_val}] {annotation.unit} "
                        f"is strictly contained within required engineering specification interval [{requirement.min_val}, {requirement.max_val}] {requirement.unit}."
                    ),
                    "review_status": "unresolved",
                    "evidence": details
                })
            else:
                # Discrepancy detected: identify whether lower bound, upper bound, or both are violated
                violations = []
                if not details["lower_bound_compliant"]:
                    violations.append(f"lower bound {annotation.min_val} < required {requirement.min_val}")
                if not details["upper_bound_compliant"]:
                    violations.append(f"upper bound {annotation.max_val} > required {requirement.max_val}")

                findings.append({
                    "rule_identifier": self.RULE_INTERVAL_CONTAINMENT,
                    "finding_type": "tolerance_interval_exceeded",
                    "severity": "error",
                    "outcome": "fail",
                    "expected_value": f"[{requirement.min_val}, {requirement.max_val}] {requirement.unit}",
                    "observed_value": f"[{annotation.min_val}, {annotation.max_val}] {annotation.unit}",
                    "deviation_value": f"Span overflow: {'; '.join(violations)}",
                    "rule_version": "1.0.0",
                    "explanation": (
                        f"Non-compliant tolerance interval: Drawing allows [{annotation.min_val}, {annotation.max_val}] {annotation.unit}, "
                        f"which violates technical specification requirement [{requirement.min_val}, {requirement.max_val}] {requirement.unit} ({'; '.join(violations)})."
                    ),
                    "review_status": "unresolved",
                    "evidence": details
                })
        else:
            # Insufficient numeric bounds to compute mathematical interval
            findings.append({
                "rule_identifier": self.RULE_INTERVAL_CONTAINMENT,
                "finding_type": "insufficient_interval_data",
                "severity": "warning",
                "outcome": "not_evaluable",
                "expected_value": f"[{requirement.min_val}, {requirement.max_val}]",
                "observed_value": annotation.original_text,
                "deviation_value": "Missing numeric tolerance limits",
                "rule_version": "1.0.0",
                "explanation": (
                    f"Drawing annotation '{annotation.original_text}' does not supply explicit numeric tolerance bounds. "
                    f"General drawing title block tolerances or engineering review required."
                ),
                "review_status": "unresolved",
                "evidence": {"drawing_text": annotation.original_text}
            })

        return findings


compliance_engine = ComplianceEngine()
