import cv2
import uuid
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
from app.config import settings
from app.services.preprocessing_service import preprocessing_service


class EvidenceService:
    """
    Evidence and provenance management:
    - Crops drawing regions for audit trails and visual citations.
    - Preserves exact mappings between PDF points, render image pixels, and viewer coordinates.
    """

    def generate_annotation_crop(
        self,
        render_image_path: str | Path,
        bbox_x0: float,
        bbox_y0: float,
        bbox_x1: float,
        bbox_y1: float,
        padding_ratio: float = 0.08
    ) -> Optional[str]:
        """
        Extracts a visual evidence crop around the annotation and stores it.
        Returns the relative path to the cropped image.
        """
        img_path = Path(render_image_path)
        if not img_path.exists():
            return None

        img = cv2.imread(str(img_path))
        if img is None:
            return None

        cropped, (px0, py0, px1, py1) = preprocessing_service.crop_normalized_bbox(
            img, bbox_x0, bbox_y0, bbox_x1, bbox_y1, padding_ratio=padding_ratio
        )

        crop_dir = settings.STORAGE_DIR / "crops"
        crop_dir.mkdir(parents=True, exist_ok=True)

        crop_filename = f"crop_{uuid.uuid4().hex[:10]}.png"
        target_path = crop_dir / crop_filename

        cv2.imwrite(str(target_path), cropped)
        rel_path = str(target_path.relative_to(Path(".")) if target_path.is_relative_to(Path(".")) else target_path)
        return rel_path

    @staticmethod
    def points_to_normalized(
        x0_pt: float, y0_pt: float, x1_pt: float, y1_pt: float,
        page_width_pt: float, page_height_pt: float
    ) -> Tuple[float, float, float, float]:
        """Converts PyMuPDF points to normalized [0.0, 1.0] coordinates."""
        nx0 = max(0.0, min(1.0, x0_pt / page_width_pt))
        ny0 = max(0.0, min(1.0, y0_pt / page_height_pt))
        nx1 = max(0.0, min(1.0, x1_pt / page_width_pt))
        ny1 = max(0.0, min(1.0, y1_pt / page_height_pt))
        return nx0, ny0, nx1, ny1

    @staticmethod
    def normalized_to_pixels(
        nx0: float, ny0: float, nx1: float, ny1: float,
        render_width_px: int, render_height_px: int
    ) -> Tuple[int, int, int, int]:
        """Converts normalized [0.0, 1.0] coordinates to raster pixel boundaries."""
        px0 = max(0, int(nx0 * render_width_px))
        py0 = max(0, int(ny0 * render_height_px))
        px1 = min(render_width_px, int(nx1 * render_width_px))
        py1 = min(render_height_px, int(ny1 * render_height_px))
        return px0, py0, px1, py1


evidence_service = EvidenceService()
