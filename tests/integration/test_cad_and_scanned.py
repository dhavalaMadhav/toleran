from pathlib import Path
import pytest
from app.services.cad_service import cad_service
from app.services.ocr_service import ocr_service
from app.services.preprocessing_service import preprocessing_service


def test_dxf_cad_parsing():
    dxf_fixture = Path("tests/fixtures/sample_drawing.dxf")
    assert dxf_fixture.exists()

    result = cad_service.parse_dxf(dxf_fixture)
    assert result["entity_count"] > 0
    assert len(result["layers"]) > 0
    assert "OUTLINE" in result["layers"]
    assert any(e["type"] == "circle" for e in result["entities"])
    assert any("20" in a["text"] for a in result["annotations"])


def test_scanned_drawing_preprocessing_and_ocr():
    png_fixture = Path("tests/fixtures/scanned_drawing.png")
    assert png_fixture.exists()

    # Verify deskewing detection
    img = preprocessing_service.load_image(png_fixture)
    deskewed, angle = preprocessing_service.deskew(img)
    assert deskewed is not None

    # Run OCR on the scanned drawing
    ocr_results = ocr_service.extract_text_regions(png_fixture, page_number=1)
    assert len(ocr_results) > 0

    # Ensure key dimensions are recognized from the scan
    texts = [res["text"] for res in ocr_results]
    assert any("20" in t for t in texts)
