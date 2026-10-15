import pytest
from app.services.tolerance_service import tolerance_service


def test_interval_containment_success():
    # Drawing interval [19.95, 20.05] is inside spec [19.9, 20.1]
    is_contained, details = tolerance_service.is_interval_contained(
        drawing_min=19.95,
        drawing_max=20.05,
        spec_min=19.90,
        spec_max=20.10
    )
    assert is_contained is True
    assert details["is_contained"] is True
    assert details["lower_bound_compliant"] is True
    assert details["upper_bound_compliant"] is True


def test_interval_containment_failure():
    # Drawing interval [19.8, 20.2] exceeds spec [19.9, 20.1]
    is_contained, details = tolerance_service.is_interval_contained(
        drawing_min=19.80,
        drawing_max=20.20,
        spec_min=19.90,
        spec_max=20.10
    )
    assert is_contained is False
    assert details["lower_bound_compliant"] is False
    assert details["upper_bound_compliant"] is False


def test_decimal_precision_exact():
    # Verify no binary floating point errors e.g. 0.1 + 0.2
    is_contained, details = tolerance_service.is_interval_contained(
        drawing_min=20.0 - 0.1,  # 19.9
        drawing_max=20.0 + 0.1,  # 20.1
        spec_min=19.9,
        spec_max=20.1
    )
    assert is_contained is True
