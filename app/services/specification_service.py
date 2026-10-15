import re
from pathlib import Path
from typing import List, Dict, Any, Optional
import fitz  # PyMuPDF
from app.core.logging import logger
from app.schemas.specification import RequirementCreate


class SpecificationService:
    """
    Parses engineering technical specification documents (PDF, text).
    Extracts structured requirements with page numbers, section headers, and exact citations.
    """

    def parse_specification_document(self, file_path: str | Path) -> List[RequirementCreate]:
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext == ".pdf":
            return self._parse_pdf_specification(path)
        else:
            return self._parse_text_specification(path)

    def _parse_pdf_specification(self, pdf_path: Path) -> List[RequirementCreate]:
        doc = fitz.open(str(pdf_path))
        requirements = []
        req_counter = 1

        for page_idx in range(len(doc)):
            page = doc[page_idx]
            page_num = page_idx + 1
            text = page.get_text()

            # Split into paragraphs/clauses
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            for para in paragraphs:
                found_reqs = self._extract_requirements_from_text(para, page_number=page_num, counter_start=req_counter)
                requirements.extend(found_reqs)
                req_counter += len(found_reqs)

        doc.close()
        return requirements

    def _parse_text_specification(self, text_path: Path) -> List[RequirementCreate]:
        with open(text_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        requirements = []
        req_counter = 1
        for para in paragraphs:
            found_reqs = self._extract_requirements_from_text(para, page_number=1, counter_start=req_counter)
            requirements.extend(found_reqs)
            req_counter += len(found_reqs)
        return requirements

    def _extract_requirements_from_text(self, text: str, page_number: int, counter_start: int) -> List[RequirementCreate]:
        reqs = []
        idx = counter_start

        # Pattern 1: Explicit Requirement code, e.g., REQ-01: Shaft diameter shall be 20 ± 0.05 mm
        # Or: "Diameter: 20 ±0.1 mm" or "Diameter must be between 19.9 mm and 20.1 mm"
        
        # Check for diameter requirement
        diam_match = re.search(r"(?:shaft|bore|hole|pin|rod)?\s*(?:diameter|OD|ID|⌀|Ø)\s*(?:shall be|must be|is|:)?\s*(\d+(?:\.\d+)?)\s*(?:±|\+/-)\s*(\d+(?:\.\d+)?)\s*(mm|in)?", text, re.IGNORECASE)
        if diam_match:
            nom = float(diam_match.group(1))
            tol = float(diam_match.group(2))
            unit = diam_match.group(3) or "mm"
            reqs.append(RequirementCreate(
                requirement_code=f"REQ-DIM-{idx:02d}",
                title=f"Diameter Requirement ({nom} ±{tol} {unit})",
                requirement_type="dimension_limit",
                nominal_value=nom,
                unit=unit,
                min_val=round(nom - tol, 4),
                max_val=round(nom + tol, 4),
                tolerance_rule="interval_containment",
                raw_text=text.strip(),
                page_number=page_number,
                section="Dimensional Specifications"
            ))
            idx += 1

        # Check for range requirement: between 19.9 and 20.1 mm or 19.8 - 20.2 mm
        range_match = re.search(r"(?:diameter|length|thickness|width|dimension|height)\s*(?:between|within)?\s*(\d+(?:\.\d+)?)\s*(?:and|to|–|-)\s*(\d+(?:\.\d+)?)\s*(mm|in)?", text, re.IGNORECASE)
        if range_match and not diam_match:
            v1 = float(range_match.group(1))
            v2 = float(range_match.group(2))
            min_v = min(v1, v2)
            max_v = max(v1, v2)
            nom = round((min_v + max_v) / 2.0, 4)
            unit = range_match.group(3) or "mm"
            reqs.append(RequirementCreate(
                requirement_code=f"REQ-RNG-{idx:02d}",
                title=f"Permissible Interval ({min_v} to {max_v} {unit})",
                requirement_type="dimension_limit",
                nominal_value=nom,
                unit=unit,
                min_val=min_v,
                max_val=max_v,
                tolerance_rule="interval_containment",
                raw_text=text.strip(),
                page_number=page_number,
                section="Dimensional Tolerances"
            ))
            idx += 1

        # Check for Thread requirements: e.g. "Thread specification: M10 x 1.5" or "Internal threads shall be M12x1.75"
        thread_match = re.search(r"(?:thread|threading|screw)\s*(?:specification|type|shall be|:)?\s*(M\d+(?:\.\d+)?)\s*(?:[xX×]\s*(\d+(?:\.\d+)?))?", text, re.IGNORECASE)
        if thread_match:
            th_name = thread_match.group(1).upper()
            pitch = thread_match.group(2)
            nom_diam = float(th_name[1:]) if len(th_name) > 1 else None
            reqs.append(RequirementCreate(
                requirement_code=f"REQ-THR-{idx:02d}",
                title=f"Thread Specification ({th_name})",
                requirement_type="thread",
                nominal_value=nom_diam,
                unit="mm",
                min_val=nom_diam,
                max_val=nom_diam,
                tolerance_rule="exact_match",
                raw_text=text.strip(),
                page_number=page_number,
                section="Fastening and Threads"
            ))
            idx += 1

        # Check for Surface finish requirements: e.g. Ra <= 0.8 um or Ra 1.6
        surface_match = re.search(r"(?:surface finish|roughness|Ra)\s*(?:<=|shall not exceed|max|:)?\s*(\d+(?:\.\d+)?)\s*(?:µm|um|micron)?", text, re.IGNORECASE)
        if surface_match:
            ra = float(surface_match.group(1))
            reqs.append(RequirementCreate(
                requirement_code=f"REQ-SFC-{idx:02d}",
                title=f"Surface Roughness Ra <= {ra} µm",
                requirement_type="surface_finish",
                nominal_value=ra,
                unit="um",
                min_val=0.0,
                max_val=ra,
                tolerance_rule="upper_limit_only",
                raw_text=text.strip(),
                page_number=page_number,
                section="Surface Texture"
            ))
            idx += 1

        return reqs


specification_service = SpecificationService()
