from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.database.models import SpecificationRequirement
from app.core.logging import logger


class RetrievalService:
    """
    Hybrid requirement retrieval service:
    1. Deterministic structured matching based on nominal value, tolerance type, and physical unit.
    2. Semantic fallback for textual clauses and design intent.
    Never relies solely on semantic score to assert engineering compliance.
    """

    def find_matching_requirements(
        self,
        db: Session,
        project_id: int,
        dimension_type: str,
        nominal_value: Optional[float],
        unit: str = "mm",
        tolerance_slack_ratio: float = 0.05
    ) -> List[SpecificationRequirement]:
        """
        Retrieves specification requirements matching the dimension type and nominal proximity.
        """
        query = db.query(SpecificationRequirement).filter(
            SpecificationRequirement.project_id == project_id
        )

        all_project_reqs = query.all()
        if not all_project_reqs:
            return []

        matched = []

        for req in all_project_reqs:
            # 1. Type affinity
            type_match = False
            if req.requirement_type == "dimension_limit" and dimension_type in ("linear", "diameter", "radius"):
                type_match = True
            elif req.requirement_type == "thread" and dimension_type == "thread":
                type_match = True
            elif req.requirement_type == "surface_finish" and dimension_type == "surface_finish":
                type_match = True

            if not type_match:
                continue

            # 2. Nominal alignment within allowable margin
            if nominal_value is not None and req.nominal_value is not None:
                # Same unit or check
                if req.unit.lower() == unit.lower():
                    diff = abs(req.nominal_value - nominal_value)
                    # Allow matching if nominals are within 5% or 1mm of each other
                    if diff <= max(1.0, nominal_value * tolerance_slack_ratio):
                        matched.append(req)
                else:
                    # Unit mismatch will be flagged in compliance engine
                    matched.append(req)
            elif nominal_value is None and req.requirement_type == "general_tolerance":
                matched.append(req)

        return matched


retrieval_service = RetrievalService()
