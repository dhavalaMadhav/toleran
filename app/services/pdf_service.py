from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import fitz  # PyMuPDF
from app.config import settings
from app.schemas.annotation import BoundingBox


class PDFService:
    """
    Format-aware PDF processor:
    - Distinguishes native vector text from scanned raster pages.
    - Extracts native text blocks with exact page coordinates.
    - Extracts vector graphics (lines, curves, rectangles) for geometric analysis.
    - Renders high-DPI raster pages for OCR and visual browser display.
    - Preserves bidirectional coordinate transformations (points <-> normalized <-> pixels).
    """

    def __init__(self, render_dpi: int = 150):
        self.render_dpi = render_dpi

    def inspect_document(self, pdf_path: str | Path) -> Dict[str, Any]:
        """Inspects PDF metadata, page count, and determines text/vector/raster distribution."""
        doc = fitz.open(str(pdf_path))
        page_count = len(doc)
        pages_info = []

        total_text_chars = 0
        total_drawings = 0

        for page_idx in range(page_count):
            page = doc[page_idx]
            rect = page.rect
            text = page.get_text()
            char_count = len(text.strip())
            total_text_chars += char_count

            drawings = page.get_drawings()
            drawing_count = len(drawings)
            total_drawings += drawing_count

            images = page.get_images()
            has_images = len(images) > 0

            # Classify page type
            if char_count > 50 and drawing_count > 10:
                page_nature = "vector_with_native_text"
            elif drawing_count > 10 and char_count <= 50:
                page_nature = "vector_without_text"
            elif has_images and char_count < 20:
                page_nature = "raster_scan"
            else:
                page_nature = "hybrid"

            pages_info.append({
                "page_number": page_idx + 1,
                "width_pt": float(rect.width),
                "height_pt": float(rect.height),
                "char_count": char_count,
                "drawing_count": drawing_count,
                "has_images": has_images,
                "page_nature": page_nature
            })

        is_searchable = total_text_chars > 30

        return {
            "page_count": page_count,
            "is_searchable": is_searchable,
            "total_text_chars": total_text_chars,
            "total_vector_drawings": total_drawings,
            "pages": pages_info
        }

    def render_page_to_image(
        self,
        pdf_path: str | Path,
        page_number: int,
        output_dir: Optional[Path] = None
    ) -> Tuple[str, int, int, float, float]:
        """
        Renders a given page to PNG image at target DPI.
        Returns: (relative_image_path, render_width_px, render_height_px, width_pt, height_pt)
        """
        if output_dir is None:
            output_dir = settings.STORAGE_DIR / "renders"
        output_dir.mkdir(parents=True, exist_ok=True)

        doc = fitz.open(str(pdf_path))
        page_idx = page_number - 1
        if page_idx < 0 or page_idx >= len(doc):
            raise IndexError(f"Page number {page_number} is out of bounds (total pages: {len(doc)})")

        page = doc[page_idx]
        rect = page.rect
        width_pt, height_pt = float(rect.width), float(rect.height)

        # Scale matrix for DPI
        zoom = self.render_dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix, alpha=False)

        stem = Path(pdf_path).stem
        image_filename = f"render_{stem}_p{page_number}_{int(width_pt)}x{int(height_pt)}.png"
        image_path = output_dir / image_filename
        pix.save(str(image_path))

        render_w, render_h = pix.width, pix.height
        doc.close()

        rel_path = str(image_path.relative_to(Path(".")) if image_path.is_relative_to(Path(".")) else image_path)
        return rel_path, render_w, render_h, width_pt, height_pt

    def extract_native_text_blocks(self, pdf_path: str | Path, page_number: int) -> List[Dict[str, Any]]:
        """
        Extracts native text blocks with bounding boxes and coordinates in points and normalized [0..1].
        """
        doc = fitz.open(str(pdf_path))
        page_idx = page_number - 1
        page = doc[page_idx]
        w_pt, h_pt = float(page.rect.width), float(page.rect.height)

        blocks = page.get_text("blocks")
        results = []

        for b in blocks:
            # b: (x0, y0, x1, y1, text, block_no, block_type)
            x0, y0, x1, y1, text, block_no, block_type = b
            clean_text = text.strip()
            if not clean_text or block_type != 0:
                continue

            norm_x0 = max(0.0, min(1.0, x0 / w_pt))
            norm_y0 = max(0.0, min(1.0, y0 / h_pt))
            norm_x1 = max(0.0, min(1.0, x1 / w_pt))
            norm_y1 = max(0.0, min(1.0, y1 / h_pt))

            results.append({
                "text": clean_text,
                "bbox_pt": [x0, y0, x1, y1],
                "bbox_norm": BoundingBox(x0=norm_x0, y0=norm_y0, x1=norm_x1, y1=norm_y1),
                "source": "native_pdf_text",
                "page_number": page_number
            })

        doc.close()
        return results

    def extract_vector_elements(self, pdf_path: str | Path, page_number: int) -> List[Dict[str, Any]]:
        """
        Extracts vector drawing objects (lines, rectangles, curves) from the PDF vector stream.
        """
        doc = fitz.open(str(pdf_path))
        page_idx = page_number - 1
        page = doc[page_idx]
        w_pt, h_pt = float(page.rect.width), float(page.rect.height)

        drawings = page.get_drawings()
        elements = []

        for d in drawings:
            rect = d.get("rect")
            if not rect:
                continue
            x0, y0, x1, y1 = rect
            norm_x0 = max(0.0, min(1.0, x0 / w_pt))
            norm_y0 = max(0.0, min(1.0, y0 / h_pt))
            norm_x1 = max(0.0, min(1.0, x1 / w_pt))
            norm_y1 = max(0.0, min(1.0, y1 / h_pt))

            elem_type = "line"
            items = d.get("items", [])
            for item in items:
                if item[0] == "c":  # curve/arc/circle
                    elem_type = "arc_or_circle"
                    break
                elif item[0] == "re":  # rectangle
                    elem_type = "rectangle"

            elements.append({
                "type": elem_type,
                "bbox_pt": [x0, y0, x1, y1],
                "bbox_norm": [norm_x0, norm_y0, norm_x1, norm_y1],
                "color": d.get("color"),
                "fill": d.get("fill"),
                "width": d.get("width", 1.0)
            })

        doc.close()
        return elements


pdf_service = PDFService()
