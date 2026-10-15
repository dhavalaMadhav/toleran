import csv
import io
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple
from sqlalchemy.orm import Session
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from app.config import settings
from app.database.models import Project, DrawingAnalysis, ExtractedAnnotation, ComplianceFinding


class ReportService:
    """Generates formal engineering compliance audit reports in PDF and CSV formats."""

    def generate_csv_report(self, db: Session, project_id: int, analysis_id: int) -> str:
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            "Annotation ID", "Page", "Callout Text", "Dimension Type", "Nominal",
            "Unit", "Upper Dev", "Lower Dev", "Min Limit", "Max Limit",
            "Tolerance Type", "Verification Status", "Confidence",
            "Finding Severity", "Finding Outcome", "Rule Identifier", "Compliance Explanation"
        ])

        annotations = db.query(ExtractedAnnotation).filter(
            ExtractedAnnotation.analysis_id == analysis_id
        ).all()

        for a in annotations:
            # Match finding if any
            finding = db.query(ComplianceFinding).filter(
                ComplianceFinding.annotation_id == a.id
            ).first()

            writer.writerow([
                a.id,
                a.page_number,
                a.original_text,
                a.dimension_type,
                a.nominal_value,
                a.unit,
                a.upper_deviation,
                a.lower_deviation,
                a.min_val,
                a.max_val,
                a.tolerance_type,
                a.verification_status,
                f"{a.confidence:.2f}",
                finding.severity if finding else "none",
                finding.outcome if finding else "pass",
                finding.rule_identifier if finding else "none",
                finding.explanation if finding else "No finding recorded."
            ])

        return output.getvalue()

    def generate_pdf_report(self, db: Session, project_id: int, analysis_id: int) -> Tuple[Path, str]:
        project = db.query(Project).filter(Project.id == project_id).first()
        analysis = db.query(DrawingAnalysis).filter(DrawingAnalysis.id == analysis_id).first()
        annotations = db.query(ExtractedAnnotation).filter(ExtractedAnnotation.analysis_id == analysis_id).all()
        findings = db.query(ComplianceFinding).filter(ComplianceFinding.analysis_id == analysis_id).all()

        reports_dir = settings.STORAGE_DIR / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        filename = f"compliance_report_proj{project_id}_analysis{analysis_id}_{uuid.uuid4().hex[:8]}.pdf"
        filepath = reports_dir / filename

        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Title"],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0f172a"),
            alignment=0
        )
        subtitle_style = ParagraphStyle(
            "ReportSubtitle",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#475569")
        )
        h2_style = ParagraphStyle(
            "H2",
            parent=styles["Heading2"],
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#1e293b"),
            spaceBefore=14,
            spaceAfter=6
        )
        cell_style = ParagraphStyle(
            "Cell",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#334155")
        )
        cell_bold = ParagraphStyle(
            "CellBold",
            parent=cell_style,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#0f172a")
        )

        story = []

        # 1. Header
        story.append(Paragraph("Engineering Drawing Intelligence & Compliance Audit", title_style))
        story.append(Spacer(1, 4))
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        story.append(Paragraph(
            f"<b>Project:</b> {project.name if project else 'N/A'} &nbsp;|&nbsp; "
            f"<b>Part:</b> {project.part_number if project and project.part_number else 'Unspecified'} ({project.revision if project else 'A'}) &nbsp;|&nbsp; "
            f"<b>Date:</b> {date_str} &nbsp;|&nbsp; "
            f"<b>Pipeline Version:</b> {analysis.pipeline_version if analysis else '1.0.0'}",
            subtitle_style
        ))
        story.append(Spacer(1, 14))

        # 2. Executive Summary Metrics
        total_ann = len(annotations)
        fail_count = sum(1 for f in findings if f.outcome == "fail")
        warn_count = sum(1 for f in findings if f.outcome in ("needs_review", "not_evaluable"))
        pass_count = sum(1 for f in findings if f.outcome == "pass")

        summary_data = [
            [
                Paragraph("<b>Metric</b>", cell_bold),
                Paragraph("<b>Count</b>", cell_bold),
                Paragraph("<b>Status Assessment</b>", cell_bold)
            ],
            [
                Paragraph("Total Extracted Annotations", cell_style),
                Paragraph(str(total_ann), cell_style),
                Paragraph("Completed extraction with provenance", cell_style)
            ],
            [
                Paragraph("Tolerance Discrepancies (Failures)", cell_style),
                Paragraph(f"<font color='red'><b>{fail_count}</b></font>", cell_style),
                Paragraph("Drawing interval exceeds engineering spec", cell_style)
            ],
            [
                Paragraph("Pending Verification (Review)", cell_style),
                Paragraph(f"<font color='#d97706'><b>{warn_count}</b></font>", cell_style),
                Paragraph("Ambiguous feature association or low confidence", cell_style)
            ],
            [
                Paragraph("Compliant Dimensions (Pass)", cell_style),
                Paragraph(f"<font color='green'><b>{pass_count}</b></font>", cell_style),
                Paragraph("Fully verified within specification interval", cell_style)
            ],
        ]

        summary_table = Table(summary_data, colWidths=[200, 80, 260])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 14))

        # 3. Compliance Findings Table
        story.append(Paragraph("Compliance Findings & Engineering Discrepancies", h2_style))
        if findings:
            finding_rows = [
                [
                    Paragraph("<b>ID / Rule</b>", cell_bold),
                    Paragraph("<b>Outcome</b>", cell_bold),
                    Paragraph("<b>Expected vs Observed</b>", cell_bold),
                    Paragraph("<b>Engineering Explanation</b>", cell_bold)
                ]
            ]
            for f in findings:
                outcome_color = "red" if f.outcome == "fail" else ("#d97706" if f.outcome == "needs_review" else "green")
                finding_rows.append([
                    Paragraph(f"<b>#{f.id}</b><br/>{f.rule_identifier}", cell_style),
                    Paragraph(f"<font color='{outcome_color}'><b>{f.outcome.upper()}</b></font><br/>{f.severity}", cell_style),
                    Paragraph(f"Exp: {f.expected_value or 'N/A'}<br/>Obs: {f.observed_value or 'N/A'}", cell_style),
                    Paragraph(f.explanation, cell_style)
                ])

            findings_table = Table(finding_rows, colWidths=[120, 80, 140, 200])
            findings_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(findings_table)
        else:
            story.append(Paragraph("No compliance discrepancies recorded for this analysis.", cell_style))

        story.append(Spacer(1, 14))

        # 4. Extracted Annotations Summary Table
        story.append(Paragraph("Extracted Dimensions & Tolerances (Top 20)", h2_style))
        ann_rows = [
            [
                Paragraph("<b>ID</b>", cell_bold),
                Paragraph("<b>Page</b>", cell_bold),
                Paragraph("<b>Callout Text</b>", cell_bold),
                Paragraph("<b>Type</b>", cell_bold),
                Paragraph("<b>Nominal</b>", cell_bold),
                Paragraph("<b>Permitted Interval</b>", cell_bold),
                Paragraph("<b>Status</b>", cell_bold)
            ]
        ]
        for a in annotations[:20]:
            interval_str = f"[{a.min_val}, {a.max_val}] {a.unit}" if a.min_val is not None else "N/A"
            ann_rows.append([
                Paragraph(str(a.id), cell_style),
                Paragraph(str(a.page_number), cell_style),
                Paragraph(f"<b>{a.original_text}</b>", cell_style),
                Paragraph(a.dimension_type, cell_style),
                Paragraph(f"{a.nominal_value} {a.unit}" if a.nominal_value else "N/A", cell_style),
                Paragraph(interval_str, cell_style),
                Paragraph(a.verification_status, cell_style),
            ])

        ann_table = Table(ann_rows, colWidths=[30, 35, 130, 75, 70, 110, 90])
        ann_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(ann_table)

        doc.build(story)
        rel_path = str(filepath.relative_to(Path(".")) if filepath.is_relative_to(Path(".")) else filepath)
        return filepath, rel_path


report_service = ReportService()
