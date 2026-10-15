from decimal import Decimal
from typing import Dict, Any, Tuple, Optional


class ToleranceService:
    """
    Mathematical tolerance interval evaluator.
    Validates interval containment, limits, and deviations without floating-point inaccuracies.
    """

    @staticmethod
    def is_interval_contained(
        drawing_min: float,
        drawing_max: float,
        spec_min: float,
        spec_max: float,
        epsilon: float = 1e-6
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Evaluates whether drawing permitted interval [drawing_min, drawing_max]
        is strictly contained within required engineering specification interval [spec_min, spec_max].
        Returns (is_contained, details_dict).
        """
        d_min = Decimal(str(drawing_min))
        d_max = Decimal(str(drawing_max))
        s_min = Decimal(str(spec_min))
        s_max = Decimal(str(spec_max))

        contained_lower = d_min >= s_min
        contained_upper = d_max <= s_max
        is_compliant = contained_lower and contained_upper

        lower_slack = float(d_min - s_min)
        upper_slack = float(s_max - d_max)

        details = {
            "drawing_interval": [float(d_min), float(d_max)],
            "spec_interval": [float(s_min), float(s_max)],
            "drawing_span": float(d_max - d_min),
            "spec_span": float(s_max - s_min),
            "lower_bound_compliant": contained_lower,
            "upper_bound_compliant": contained_upper,
            "lower_slack": lower_slack,
            "upper_slack": upper_slack,
            "is_contained": is_compliant
        }
        return is_compliant, details

    @staticmethod
    def calculate_nominal_deviation(drawing_nominal: float, spec_nominal: float) -> Tuple[float, float]:
        """Calculates absolute and relative deviation between nominal values."""
        d = Decimal(str(drawing_nominal))
        s = Decimal(str(spec_nominal))
        diff = d - s
        rel = (diff / s) * Decimal(100) if s != Decimal(0) else Decimal(0)
        return float(diff), float(rel)


tolerance_service = ToleranceService()
