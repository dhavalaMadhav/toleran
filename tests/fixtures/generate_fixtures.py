import os
from pathlib import Path
import fitz  # PyMuPDF
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import cv2
import numpy as np
import ezdxf


def generate_synthetic_fixtures(output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate Clean Vector Engineering Drawing PDF
    pdf_path = output_dir / "synthetic_drawing.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=(800, 600))

    # Border & Title block
    c.setLineWidth(2)
    c.rect(20, 20, 760, 560)
    c.rect(500, 20, 280, 80)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(510, 80, "TITLE: FLANGE SHAFT ASSEMBLY")
    c.setFont("Helvetica", 9)
    c.drawString(510, 65, "DWG NO: AERO-SH-7740")
    c.drawString(510, 50, "REVISION: Rev B")
    c.drawString(510, 35, "UNITS: mm  |  GENERAL TOL: +/- 0.2")

    # Geometric Features
    # Shaft Body: Rectangle
    c.setLineWidth(1.5)
    c.rect(150, 250, 300, 100)

    # Bore: Concentric Circles
    c.circle(300, 300, 40)
    c.circle(300, 300, 15)

    # Dimension 1: Diameter Callout on Shaft "⌀20 ±0.1 mm"
    c.setFont("Helvetica-Bold", 11)
    c.drawString(270, 390, "%%C20 +/-0.1 mm")
    # Leader line pointing to circle
    c.setLineWidth(1)
    c.line(265, 385, 300, 340)

    # Dimension 2: Length Dimension "50 +0.2/-0.1 mm"
    c.drawString(260, 225, "50 +0.2/-0.1 mm")
    # Dimension line
    c.line(150, 235, 450, 235)
    c.line(150, 230, 150, 248)
    c.line(450, 230, 450, 248)

    # Dimension 3: Limit Dimension "19.9-20.1 mm"
    c.drawString(160, 420, "19.9-20.1 mm")

    # Dimension 4: Radius Callout "R5"
    c.drawString(460, 320, "R5")

    # Dimension 5: Thread Callout "M10 x 1.5"
    c.drawString(100, 180, "M10 x 1.5")

    # Dimension 6: Angular Callout "45 deg +/-0.5 deg"
    c.drawString(100, 150, "45 deg +/-0.5 deg")

    c.save()

    # 2. Generate Scanned Drawing Image (PNG with slight tilt)
    png_path = output_dir / "scanned_drawing.png"
    # Render page 1 of synthetic PDF to image using PyMuPDF
    doc = fitz.open(str(pdf_path))
    page = doc[0]
    pix = page.get_pixmap(dpi=150)
    img_data = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.h, pix.w, pix.n))
    if pix.n == 4:
        img_data = cv2.cvtColor(img_data, cv2.COLOR_RGBA2BGR)
    elif pix.n == 3:
        img_data = cv2.cvtColor(img_data, cv2.COLOR_RGB2BGR)

    # Add slight rotation of 1.5 degrees
    (h, w) = img_data.shape[:2]
    matrix = cv2.getRotationMatrix2D((w // 2, h // 2), 1.5, 1.0)
    tilted = cv2.warpAffine(img_data, matrix, (w, h), borderValue=(255, 255, 255))
    cv2.imwrite(str(png_path), tilted)
    doc.close()

    # 3. Generate Technical Specification PDF
    spec_pdf_path = output_dir / "technical_specification.pdf"
    sc = canvas.Canvas(str(spec_pdf_path), pagesize=letter)
    sc.setFont("Helvetica-Bold", 14)
    sc.drawString(50, 750, "AEROSPACE TRANSMISSION ENGINEERING SPECIFICATION")
    sc.setFont("Helvetica-Bold", 11)
    sc.drawString(50, 720, "PART: AERO-SH-7740 (REVISION B)")

    sc.setFont("Helvetica-Bold", 11)
    sc.drawString(50, 680, "Section 1: Dimensional Constraints")
    sc.setFont("Helvetica", 10)
    sc.drawString(50, 660, "REQ-DIM-01: Shaft journal diameter shall be 20 +/-0.05 mm.")
    sc.drawString(50, 640, "REQ-DIM-02: Total body length dimension between 49.8 and 50.3 mm.")

    sc.setFont("Helvetica-Bold", 11)
    sc.drawString(50, 600, "Section 2: Fastening and Thread Specifications")
    sc.setFont("Helvetica", 10)
    sc.drawString(50, 580, "REQ-THR-01: External mounting thread specification shall be M10 x 1.5.")

    sc.setFont("Helvetica-Bold", 11)
    sc.drawString(50, 540, "Section 3: Surface Texture")
    sc.setFont("Helvetica", 10)
    sc.drawString(50, 520, "REQ-SFC-01: Bearing seat surface finish Ra <= 0.8 um.")

    sc.save()

    # 4. Generate Valid CAD DXF File
    dxf_path = output_dir / "sample_drawing.dxf"
    dxf_doc = ezdxf.new(dxfversion="R2010")
    msp = dxf_doc.modelspace()
    msp.add_line((0, 0), (100, 0), dxfattribs={"layer": "OUTLINE"})
    msp.add_line((100, 0), (100, 50), dxfattribs={"layer": "OUTLINE"})
    msp.add_line((100, 50), (0, 50), dxfattribs={"layer": "OUTLINE"})
    msp.add_line((0, 50), (0, 0), dxfattribs={"layer": "OUTLINE"})
    msp.add_circle((50, 25), 10, dxfattribs={"layer": "HOLES"})
    msp.add_text("%%C20 +/-0.1", dxfattribs={"layer": "DIMENSIONS", "height": 3.5}).set_placement((45, 40))
    dxf_doc.saveas(str(dxf_path))

    print(f"Generated synthetic test fixtures in: {output_dir}")


if __name__ == "__main__":
    generate_synthetic_fixtures(Path("tests/fixtures"))
