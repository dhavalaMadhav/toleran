import os
import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from openai import OpenAI
from app.config import settings
from app.database.models import (
    Project, Document, ExtractedAnnotation, SpecificationRequirement,
    ComplianceFinding, ReviewDecision, CopilotConversation, CopilotMessage
)
from app.schemas.copilot import Citation, CopilotChatResponse
from app.core.logging import logger


class CopilotService:
    """
    Project-aware Engineering Copilot with grounded RAG and strict citation enforcement.
    Retrieves annotations, specification requirements, compliance findings, and review records.
    Answers strictly cite persisted database provenance and never hallucinate.
    """

    def __init__(self):
        self.api_key = settings.LLM_API_KEY or os.environ.get("OPENAI_API_KEY")
        self.model = settings.LLM_MODEL or "gpt-4o"

    def process_query(
        self,
        db: Session,
        project_id: int,
        query: str,
        conversation_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> CopilotChatResponse:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"Project #{project_id} not found.")

        # Ensure conversation exists
        if conversation_id:
            conv = db.query(CopilotConversation).filter(
                CopilotConversation.id == conversation_id,
                CopilotConversation.project_id == project_id
            ).first()
        else:
            conv = None

        if not conv:
            conv = CopilotConversation(
                project_id=project_id,
                user_id=user_id,
                title=f"Chat: {query[:40]}..."
            )
            db.add(conv)
            db.commit()
            db.refresh(conv)

        # 1. Retrieve project context tools
        annotations = db.query(ExtractedAnnotation).join(ExtractedAnnotation.analysis).filter(
            ExtractedAnnotation.analysis.has(project_id=project_id)
        ).all()

        findings = db.query(ComplianceFinding).filter(
            ComplianceFinding.project_id == project_id
        ).all()

        requirements = db.query(SpecificationRequirement).filter(
            SpecificationRequirement.project_id == project_id
        ).all()

        documents = db.query(Document).filter(
            Document.project_id == project_id
        ).all()

        doc_names = {d.id: d.original_filename for d in documents}

        # 2. Match tools / context relevant to the user query
        q_lower = query.lower()
        citations: List[Citation] = []
        tools_called = []

        # Grounding context builder
        context_lines = []
        context_lines.append(f"PROJECT: {project.name} (Part: {project.part_number or 'N/A'}, Rev: {project.revision})")
        context_lines.append(f"TOTAL EXTRACTED ANNOTATIONS: {len(annotations)}")
        context_lines.append(f"TOTAL SPECIFICATION REQUIREMENTS: {len(requirements)}")
        context_lines.append(f"TOTAL COMPLIANCE FINDINGS: {len(findings)}")

        # Collect relevant citations based on query intent
        relevant_annotations = []
        relevant_findings = []
        relevant_requirements = []

        # Check for diameter query
        if "diameter" in q_lower or "⌀" in q_lower or "dia" in q_lower:
            tools_called.append({"tool": "filter_annotations_by_type", "type": "diameter"})
            for a in annotations:
                if a.dimension_type == "diameter":
                    relevant_annotations.append(a)
                    citations.append(Citation(
                        source_type="drawing_annotation",
                        document_name=doc_names.get(a.analysis.document_id, "Drawing"),
                        page_number=a.page_number,
                        identifier=f"Annotation #{a.id}",
                        target_id=a.id,
                        excerpt_or_value=a.original_text,
                        bbox={"x0": a.bbox_x0, "y0": a.bbox_y0, "x1": a.bbox_x1, "y1": a.bbox_y1}
                    ))

        # Check for review query
        if "review" in q_lower or "pending" in q_lower or "unresolved" in q_lower or "ambiguous" in q_lower:
            tools_called.append({"tool": "get_pending_reviews"})
            for a in annotations:
                if a.verification_status in ("pending_review", "rejected") or a.is_ambiguous:
                    if a not in relevant_annotations:
                        relevant_annotations.append(a)
                        citations.append(Citation(
                            source_type="drawing_annotation",
                            document_name=doc_names.get(a.analysis.document_id, "Drawing"),
                            page_number=a.page_number,
                            identifier=f"Annotation #{a.id} ({a.verification_status})",
                            target_id=a.id,
                            excerpt_or_value=f"{a.original_text}: {a.ambiguity_reason or 'Verification needed'}",
                            bbox={"x0": a.bbox_x0, "y0": a.bbox_y0, "x1": a.bbox_x1, "y1": a.bbox_y1}
                        ))

        # Check for tolerance / finding / flag query
        if "finding" in q_lower or "flag" in q_lower or "tolerance" in q_lower or "fail" in q_lower or "discrepancy" in q_lower:
            tools_called.append({"tool": "get_compliance_findings"})
            for f in findings:
                relevant_findings.append(f)
                citations.append(Citation(
                    source_type="compliance_finding",
                    document_name="Compliance Audit",
                    page_number=1,
                    identifier=f"Finding #{f.id} [{f.severity.upper()}]",
                    target_id=f.id,
                    excerpt_or_value=f"{f.finding_type}: {f.explanation}"
                ))

        # If general question, populate top annotations and findings
        if not relevant_annotations and not relevant_findings:
            tools_called.append({"tool": "get_project_summary"})
            for a in annotations[:5]:
                relevant_annotations.append(a)
                citations.append(Citation(
                    source_type="drawing_annotation",
                    document_name=doc_names.get(a.analysis.document_id, "Drawing"),
                    page_number=a.page_number,
                    identifier=f"Annotation #{a.id}",
                    target_id=a.id,
                    excerpt_or_value=a.original_text,
                    bbox={"x0": a.bbox_x0, "y0": a.bbox_y0, "x1": a.bbox_x1, "y1": a.bbox_y1}
                ))
            for f in findings[:5]:
                relevant_findings.append(f)

        # Build grounded response
        if self.api_key:
            response_content = self._generate_llm_response(
                query=query,
                project=project,
                annotations=relevant_annotations or annotations[:15],
                findings=relevant_findings or findings[:15],
                requirements=requirements[:15],
                citations=citations
            )
        else:
            response_content = self._generate_deterministic_response(
                query=query,
                project=project,
                annotations=relevant_annotations or annotations,
                findings=relevant_findings or findings,
                requirements=requirements,
                citations=citations
            )

        # Persist user message and assistant reply
        user_msg = CopilotMessage(
            conversation_id=conv.id,
            role="user",
            content=query
        )
        asst_msg = CopilotMessage(
            conversation_id=conv.id,
            role="assistant",
            content=response_content,
            citations_json=[c.model_dump() for c in citations],
            tools_called_json=tools_called
        )
        db.add(user_msg)
        db.add(asst_msg)
        db.commit()
        db.refresh(asst_msg)

        return CopilotChatResponse(
            conversation_id=conv.id,
            message_id=asst_msg.id,
            content=response_content,
            citations=citations,
            tools_called=tools_called,
            created_at=asst_msg.created_at
        )

    def _generate_deterministic_response(
        self,
        query: str,
        project: Project,
        annotations: List[ExtractedAnnotation],
        findings: List[ComplianceFinding],
        requirements: List[SpecificationRequirement],
        citations: List[Citation]
    ) -> str:
        """Deterministic, grounded responses with exact facts, calculations, and citations."""
        q = query.lower()

        # Dimension / Diameter query
        if "diameter" in q or "⌀" in q:
            diams = [a for a in annotations if a.dimension_type == "diameter"]
            if diams:
                items = "\n".join([f"- **[Annotation #{a.id}]** `{a.original_text}` (Nominal: {a.nominal_value} {a.unit}, Range: [{a.min_val}, {a.max_val}] {a.unit}, Page {a.page_number})" for a in diams])
                return (
                    f"### Extracted Diameter Dimensions\n\n"
                    f"Identified {len(diams)} diameter callout(s) in project **{project.name}**:\n\n"
                    f"{items}\n\n"
                    f"> **Evidence Grounding**: Citations are linked directly to visual drawing coordinates."
                )
            return f"No diameter dimensions were detected in the uploaded drawings for project **{project.name}**."

        # Review / Ambiguous query
        if "review" in q or "pending" in q or "ambiguous" in q:
            pending = [a for a in annotations if a.verification_status in ("pending_review", "rejected") or a.is_ambiguous]
            if pending:
                items = "\n".join([f"- **[Annotation #{a.id}]** `{a.original_text}` — Status: `{a.verification_status}` (Reason: {a.ambiguity_reason or 'Awaiting engineer sign-off'})" for a in pending])
                return (
                    f"### Items Requiring Engineering Review\n\n"
                    f"Found {len(pending)} annotation(s) requiring verification:\n\n"
                    f"{items}\n\n"
                    f"You can review, correct, or approve these directly in the **Review Queue**."
                )
            return "All extracted annotations have met automated verification thresholds. No items are currently pending review."

        # Findings / Tolerance / Discrepancy query
        if "finding" in q or "flag" in q or "tolerance" in q or "why" in q or "discrepancy" in q:
            if findings:
                fails = [f for f in findings if f.outcome == "fail"]
                warns = [f for f in findings if f.outcome in ("needs_review", "not_evaluable")]
                passes = [f for f in findings if f.outcome == "pass"]

                summary_bullets = []
                for f in findings:
                    status_badge = "❌ FAIL" if f.outcome == "fail" else ("⚠️ REVIEW" if f.outcome == "needs_review" else "✅ PASS")
                    summary_bullets.append(
                        f"- **[Finding #{f.id}] {status_badge}** (`{f.rule_identifier}`): {f.explanation}\n"
                        f"  - *Expected*: `{f.expected_value or 'N/A'}` | *Observed*: `{f.observed_value or 'N/A'}`"
                    )

                return (
                    f"### Compliance Findings Analysis\n\n"
                    f"The compliance engine evaluated project **{project.name}** against technical specifications:\n\n"
                    f"- **Violations (Failures)**: {len(fails)}\n"
                    f"- **Pending Verification**: {len(warns)}\n"
                    f"- **Conforming**: {len(passes)}\n\n"
                    f"#### Breakdown:\n" + "\n".join(summary_bullets)
                )
            return "No compliance discrepancies have been flagged for this project."

        # Default general project overview
        return (
            f"### Project Overview: {project.name}\n\n"
            f"- **Part Number**: {project.part_number or 'Unspecified'} ({project.revision})\n"
            f"- **Extracted Dimensions**: {len(annotations)} total records\n"
            f"- **Specification Requirements**: {len(requirements)} clauses parsed\n"
            f"- **Compliance Findings**: {len(findings)} evaluated rules\n\n"
            f"You can ask me specific questions regarding tolerances (e.g. *'Why was this tolerance flagged?'*), "
            f"dimension queries (*'List all diameter dimensions'*), or review status (*'Which items need review?'*)."
        )

    def _generate_llm_response(
        self,
        query: str,
        project: Project,
        annotations: List[ExtractedAnnotation],
        findings: List[ComplianceFinding],
        requirements: List[SpecificationRequirement],
        citations: List[Citation]
    ) -> str:
        """Queries OpenAI API with strictly grounded facts and citation instructions."""
        try:
            client = OpenAI(api_key=self.api_key, timeout=30.0)

            context_data = {
                "project": {"name": project.name, "part": project.part_number, "revision": project.revision},
                "annotations": [
                    {
                        "id": a.id, "text": a.original_text, "type": a.dimension_type,
                        "nominal": a.nominal_value, "unit": a.unit, "min": a.min_val, "max": a.max_val,
                        "page": a.page_number, "status": a.verification_status, "reason": a.ambiguity_reason
                    }
                    for a in annotations
                ],
                "findings": [
                    {
                        "id": f.id, "rule": f.rule_identifier, "outcome": f.outcome,
                        "severity": f.severity, "expected": f.expected_value, "observed": f.observed_value,
                        "explanation": f.explanation
                    }
                    for f in findings
                ],
                "requirements": [
                    {
                        "code": r.requirement_code, "title": r.title, "nominal": r.nominal_value,
                        "min": r.min_val, "max": r.max_val, "unit": r.unit
                    }
                    for r in requirements
                ]
            }

            prompt = (
                "You are an Engineering Drawing Intelligence Copilot. Answer the engineer's question based strictly on the provided JSON project data.\n"
                "RULES:\n"
                "1. Cite exact IDs, e.g. [Annotation #12], [Finding #3], [REQ-DIM-01].\n"
                "2. Clearly separate: (A) Facts extracted from documents, (B) Deterministic calculation outcomes, and (C) Engineering recommendations.\n"
                "3. If evidence is not in the data, state: 'Evidence is not available in the uploaded project documents.' Never fabricate.\n"
                f"PROJECT DATA:\n{context_data}\n\n"
                f"QUESTION: {query}"
            )

            res = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a precise, grounded mechanical engineering assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=600
            )
            return res.choices[0].message.content or "No response generated."
        except Exception as e:
            logger.warning(f"Copilot LLM synthesis failed: {e}. Falling back to deterministic reasoning.")
            return self._generate_deterministic_response(
                query, project, annotations, findings, requirements, citations
            )


copilot_service = CopilotService()
