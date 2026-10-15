import pytest
from app.services.dimension_parser import dimension_parser


def test_parse_plain_nominal():
    ann = dimension_parser.parse("20 mm")
    assert ann.dimension_type == "linear"
    assert ann.nominal_value == 20.0
    assert ann.unit == "mm"
    assert ann.upper_deviation == 0.0
    assert ann.lower_deviation == 0.0
    assert ann.min_val == 20.0
    assert ann.max_val == 20.0


def test_parse_bilateral_tolerance():
    ann = dimension_parser.parse("20 +/- 0.1 mm")
    assert ann.dimension_type == "linear"
    assert ann.nominal_value == 20.0
    assert ann.tolerance_type == "bilateral"
    assert ann.upper_deviation == 0.1
    assert ann.lower_deviation == -0.1
    assert ann.min_val == 19.9
    assert ann.max_val == 20.1


def test_parse_asymmetric_tolerance():
    ann = dimension_parser.parse("20 +0.2/-0.1 mm")
    assert ann.dimension_type == "linear"
    assert ann.nominal_value == 20.0
    assert ann.tolerance_type == "asymmetric"
    assert ann.upper_deviation == 0.2
    assert ann.lower_deviation == -0.1
    assert ann.min_val == 19.9
    assert ann.max_val == 20.2


def test_parse_diameter_callout():
    ann = dimension_parser.parse("%%C20 +/-0.1 mm")
    assert ann.dimension_type == "diameter"
    assert ann.nominal_value == 20.0
    assert ann.min_val == 19.9
    assert ann.max_val == 20.1


def test_parse_limit_dimension():
    ann = dimension_parser.parse("19.9-20.1 mm")
    assert ann.tolerance_type == "limit"
    assert ann.nominal_value == 20.0
    assert ann.min_val == 19.9
    assert ann.max_val == 20.1


def test_parse_radius():
    ann = dimension_parser.parse("R5")
    assert ann.dimension_type == "radius"
    assert ann.nominal_value == 5.0


def test_parse_thread():
    ann = dimension_parser.parse("M10 x 1.5")
    assert ann.dimension_type == "thread"
    assert ann.nominal_value == 10.0


def test_parse_angular():
    ann = dimension_parser.parse("45 deg +/-0.5 deg")
    assert ann.dimension_type == "angular"
    assert ann.nominal_value == 45.0
    assert ann.min_val == 44.5
    assert ann.max_val == 45.5


def test_ambiguous_callout():
    ann = dimension_parser.parse("SPECIAL NOTE INSPECT CLOSELY")
    assert ann.is_ambiguous is True
    assert ann.verification_status == "pending_review"
    assert ann.dimension_type == "general_note"
