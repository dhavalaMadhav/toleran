import pytest
from app.services.evidence_service import evidence_service


def test_coordinate_transforms_points_to_norm():
    # PDF page of 800x600 pt
    page_w, page_h = 800.0, 600.0
    x0_pt, y0_pt, x1_pt, y1_pt = 200.0, 150.0, 400.0, 300.0

    nx0, ny0, nx1, ny1 = evidence_service.points_to_normalized(
        x0_pt, y0_pt, x1_pt, y1_pt, page_w, page_h
    )

    assert nx0 == 0.25
    assert ny0 == 0.25
    assert nx1 == 0.50
    assert ny1 == 0.50


def test_coordinate_transforms_norm_to_pixels():
    # Rendered raster of 1600x1200 px
    rw, rh = 1600, 1200
    nx0, ny0, nx1, ny1 = 0.25, 0.25, 0.50, 0.50

    px0, py0, px1, py1 = evidence_service.normalized_to_pixels(
        nx0, ny0, nx1, ny1, rw, rh
    )

    assert px0 == 400
    assert py0 == 300
    assert px1 == 800
    assert py1 == 600
