import re
from decimal import Decimal, InvalidOperation
from typing import Optional, Dict, Any, Tuple
from app.schemas.annotation import NormalizedDimension, BoundingBox


class DimensionParser:
    """
    Deterministic engineering dimension and tolerance parser.
    Uses Decimal arithmetic to guarantee zero precision loss in tolerance intervals.
    """

    # Common unicode and ASCII diameter symbols
    DIAMETER_PREFIX = r"(?:[⌀Øø]|%%[cC]|DIA\.?|dia\.?)\s*"
    # Radius prefix
    RADIUS_PREFIX = r"(?:[Rr]|RAD\.?)\s*"
    # Plus/minus symbol variants
    PLUS_MINUS = r"(?:±|\+/-|\+\s*-\s*)"
    # Units
    UNIT_PATTERN = r"(?:\s*(mm|in|inch|\"|deg|°))?"

    def parse(
        self,
        raw_text: str,
        bbox: Optional[BoundingBox] = None,
        page_number: int = 1,
        extraction_method: str = "ocr",
        confidence: float = 0.90,
        drawing_default_unit: str = "mm"
    ) -> NormalizedDimension:
        text = raw_text.strip()
        if not bbox:
            bbox = BoundingBox(x0=0.0, y0=0.0, x1=1.0, y1=1.0)

        # 1. Thread Callouts: e.g. M10 x 1.5, M12x1.75 - 6H
        thread_match = re.search(r"^(M\d+(?:\.\d+)?)\s*(?:[xX×]\s*(\d+(?:\.\d+)?))?(?:\s*-\s*([0-9A-Za-z]+))?", text)
        if thread_match:
            thread_size = thread_match.group(1)
            pitch = thread_match.group(2)
            tol_class = thread_match.group(3) or "standard"
            try:
                nom = Decimal(thread_size[1:])
            except Exception:
                nom = None
            return NormalizedDimension(
                original_text=text,
                dimension_type="thread",
                nominal_value=float(nom) if nom else None,
                unit=drawing_default_unit,
                upper_deviation=0.0,
                lower_deviation=0.0,
                min_val=float(nom) if nom else None,
                max_val=float(nom) if nom else None,
                tolerance_type="thread_class",
                page_number=page_number,
                bbox=bbox,
                extraction_method=extraction_method,
                confidence=confidence,
                is_ambiguous=False,
                verification_status="auto_accepted" if confidence >= 0.88 else "pending_review"
            )

        # 2. Limit Dimensions: e.g. 19.9–20.1, 19.9 - 20.1, 19.9 TO 20.1
        limit_match = re.search(r"^(?:" + self.DIAMETER_PREFIX + r")?(\d+(?:\.\d+)?)\s*(?:[–—\-]|TO)\s*(\d+(?:\.\d+)?)" + self.UNIT_PATTERN + r"$", text, re.IGNORECASE)
        if limit_match:
            try:
                v1 = Decimal(limit_match.group(1))
                v2 = Decimal(limit_match.group(2))
                min_v = min(v1, v2)
                max_v = max(v1, v2)
                nom = (min_v + max_v) / Decimal(2)
                unit = limit_match.group(3) or drawing_default_unit
                dim_type = "diameter" if re.search(self.DIAMETER_PREFIX, text) else "linear"
                upper_dev = max_v - nom
                lower_dev = min_v - nom
                return NormalizedDimension(
                    original_text=text,
                    dimension_type=dim_type,
                    nominal_value=float(nom),
                    unit=unit,
                    upper_deviation=float(upper_dev),
                    lower_deviation=float(lower_dev),
                    min_val=float(min_v),
                    max_val=float(max_v),
                    tolerance_type="limit",
                    page_number=page_number,
                    bbox=bbox,
                    extraction_method=extraction_method,
                    confidence=confidence,
                    is_ambiguous=False,
                    verification_status="auto_accepted" if confidence >= 0.88 else "pending_review"
                )
            except (InvalidOperation, ValueError):
                pass

        # 3. Asymmetric Tolerances: e.g. 20 +0.2/-0.1, 20 +0.2 -0.1, ⌀20 +0.05/-0.02
        asym_match = re.search(
            r"^(" + self.DIAMETER_PREFIX + r"|" + self.RADIUS_PREFIX + r")?"
            r"(\d+(?:\.\d+)?)\s*"
            r"(?:\+|\^)\s*(\d+(?:\.\d+)?)\s*(?:/|\s*)\s*-\s*(\d+(?:\.\d+)?)"
            + self.UNIT_PATTERN + r"$",
            text
        )
        if asym_match:
            try:
                prefix = asym_match.group(1) or ""
                nom = Decimal(asym_match.group(2))
                upper_d = Decimal(asym_match.group(3))
                lower_d = -Decimal(asym_match.group(4))
                min_v = nom + lower_d
                max_v = nom + upper_d
                unit = asym_match.group(5) or drawing_default_unit
                dim_type = "diameter" if re.search(self.DIAMETER_PREFIX, prefix) else ("radius" if re.search(self.RADIUS_PREFIX, prefix) else "linear")
                return NormalizedDimension(
                    original_text=text,
                    dimension_type=dim_type,
                    nominal_value=float(nom),
                    unit=unit,
                    upper_deviation=float(upper_d),
                    lower_deviation=float(lower_d),
                    min_val=float(min_v),
                    max_val=float(max_v),
                    tolerance_type="asymmetric",
                    page_number=page_number,
                    bbox=bbox,
                    extraction_method=extraction_method,
                    confidence=confidence,
                    is_ambiguous=False,
                    verification_status="auto_accepted" if confidence >= 0.88 else "pending_review"
                )
            except (InvalidOperation, ValueError):
                pass

        # 4. Bilateral Tolerances: e.g. 20 ±0.1, ⌀20 ±0.1, R5 ±0.05 mm
        bilat_match = re.search(
            r"^(" + self.DIAMETER_PREFIX + r"|" + self.RADIUS_PREFIX + r")?"
            r"(\d+(?:\.\d+)?)\s*"
            + self.PLUS_MINUS +
            r"\s*(\d+(?:\.\d+)?)"
            + self.UNIT_PATTERN + r"$",
            text
        )
        if bilat_match:
            try:
                prefix = bilat_match.group(1) or ""
                nom = Decimal(bilat_match.group(2))
                tol = Decimal(bilat_match.group(3))
                upper_d = tol
                lower_d = -tol
                min_v = nom - tol
                max_v = nom + tol
                unit = bilat_match.group(4) or drawing_default_unit
                dim_type = "diameter" if re.search(self.DIAMETER_PREFIX, prefix) else ("radius" if re.search(self.RADIUS_PREFIX, prefix) else "linear")
                return NormalizedDimension(
                    original_text=text,
                    dimension_type=dim_type,
                    nominal_value=float(nom),
                    unit=unit,
                    upper_deviation=float(upper_d),
                    lower_deviation=float(lower_d),
                    min_val=float(min_v),
                    max_val=float(max_v),
                    tolerance_type="bilateral",
                    page_number=page_number,
                    bbox=bbox,
                    extraction_method=extraction_method,
                    confidence=confidence,
                    is_ambiguous=False,
                    verification_status="auto_accepted" if confidence >= 0.88 else "pending_review"
                )
            except (InvalidOperation, ValueError):
                pass

        # 5. Angular Dimensions: e.g. 45° ±0.5°, 90°, 45 DEG, 45 deg +/-0.5 deg
        angular_match = re.search(r"^(\d+(?:\.\d+)?)\s*(?:°|deg|DEG)(?:\s*" + self.PLUS_MINUS + r"\s*(\d+(?:\.\d+)?)\s*(?:°|deg|DEG)?)?$", text, re.IGNORECASE)
        if angular_match:
            try:
                nom = Decimal(angular_match.group(1))
                tol = Decimal(angular_match.group(2)) if angular_match.group(2) else Decimal("0.0")
                return NormalizedDimension(
                    original_text=text,
                    dimension_type="angular",
                    nominal_value=float(nom),
                    unit="deg",
                    upper_deviation=float(tol),
                    lower_deviation=-float(tol),
                    min_val=float(nom - tol),
                    max_val=float(nom + tol),
                    tolerance_type="bilateral" if tol > 0 else "basic",
                    page_number=page_number,
                    bbox=bbox,
                    extraction_method=extraction_method,
                    confidence=confidence,
                    is_ambiguous=False,
                    verification_status="auto_accepted" if confidence >= 0.88 else "pending_review"
                )
            except (InvalidOperation, ValueError):
                pass

        # 6. Diameter or Radius Nominal without explicit tolerance: e.g. ⌀20, Ø25, R10, RAD 5
        prefixed_nominal = re.search(r"^(" + self.DIAMETER_PREFIX + r"|" + self.RADIUS_PREFIX + r")(\d+(?:\.\d+)?)" + self.UNIT_PATTERN + r"$", text)
        if prefixed_nominal:
            try:
                prefix = prefixed_nominal.group(1)
                nom = Decimal(prefixed_nominal.group(2))
                unit = prefixed_nominal.group(3) or drawing_default_unit
                dim_type = "diameter" if re.search(self.DIAMETER_PREFIX, prefix) else "radius"
                return NormalizedDimension(
                    original_text=text,
                    dimension_type=dim_type,
                    nominal_value=float(nom),
                    unit=unit,
                    upper_deviation=0.0,
                    lower_deviation=0.0,
                    min_val=float(nom),
                    max_val=float(nom),
                    tolerance_type="unspecified",
                    page_number=page_number,
                    bbox=bbox,
                    extraction_method=extraction_method,
                    confidence=confidence * 0.95,
                    is_ambiguous=False,
                    verification_status="pending_review"
                )
            except (InvalidOperation, ValueError):
                pass

        # 7. Plain Linear Nominal: e.g. 20, 50.5 mm
        plain_nominal = re.search(r"^(\d+(?:\.\d+)?)" + self.UNIT_PATTERN + r"$", text)
        if plain_nominal:
            try:
                nom = Decimal(plain_nominal.group(1))
                unit = plain_nominal.group(2) or drawing_default_unit
                return NormalizedDimension(
                    original_text=text,
                    dimension_type="linear",
                    nominal_value=float(nom),
                    unit=unit,
                    upper_deviation=0.0,
                    lower_deviation=0.0,
                    min_val=float(nom),
                    max_val=float(nom),
                    tolerance_type="unspecified",
                    page_number=page_number,
                    bbox=bbox,
                    extraction_method=extraction_method,
                    confidence=confidence,
                    is_ambiguous=False,
                    verification_status="pending_review"
                )
            except (InvalidOperation, ValueError):
                pass

        # Fallback: General note or unparsed annotation requiring engineering review
        return NormalizedDimension(
            original_text=text,
            dimension_type="general_note",
            nominal_value=None,
            unit=drawing_default_unit,
            upper_deviation=None,
            lower_deviation=None,
            min_val=None,
            max_val=None,
            tolerance_type="unspecified",
            page_number=page_number,
            bbox=bbox,
            extraction_method=extraction_method,
            confidence=max(confidence * 0.5, 0.20),
            is_ambiguous=True,
            ambiguity_reason=f"Callout pattern '{text}' does not match recognized mechanical dimension standard formats.",
            verification_status="pending_review"
        )


dimension_parser = DimensionParser()
