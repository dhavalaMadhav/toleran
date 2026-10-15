from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
from rapidocr_onnxruntime import RapidOCR
from app.config import settings
from app.core.logging import logger
from app.schemas.annotation import BoundingBox
from app.services.preprocessing_service import preprocessing_service


class OCRService:
    """
    OCR engine wrapping RapidOCR (PaddleOCR ONNX weights).
    Extracts text, bounding polygon, normalized coordinates, and calibrated confidence.
    """

    def __init__(self):
        self._engine: Optional[RapidOCR] = None

    @property
    def engine(self) -> RapidOCR:
        if self._engine is None:
            logger.info("Initializing RapidOCR ONNX engine...")
            self._engine = RapidOCR()
        return self._engine

    def extract_text_regions(
        self,
        image_input: str | Path | np.ndarray,
        page_number: int = 1,
        min_confidence: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Runs OCR on an image and returns detected text boxes with normalized coordinates [0..1].
        """
        if min_confidence is None:
            min_confidence = settings.OCR_CONFIDENCE_THRESHOLD

        img = preprocessing_service.load_image(image_input)
        h, w = img.shape[:2]

        enhanced = preprocessing_service.enhance_for_ocr(img)

        try:
            results, elapse = self.engine(enhanced)
        except Exception as e:
            logger.error(f"OCR execution failed: {e}")
            return []

        if not results:
            return []

        extracted_boxes = []

        for item in results:
            dt_box, text, score = item
            clean_text = text.strip()
            score_val = float(score)

            if not clean_text or score_val < min_confidence:
                continue

            pts = np.array(dt_box, dtype=np.float32)
            min_x = float(np.min(pts[:, 0]))
            max_x = float(np.max(pts[:, 0]))
            min_y = float(np.min(pts[:, 1]))
            max_y = float(np.max(pts[:, 1]))

            norm_x0 = max(0.0, min(1.0, min_x / w))
            norm_y0 = max(0.0, min(1.0, min_y / h))
            norm_x1 = max(0.0, min(1.0, max_x / w))
            norm_y1 = max(0.0, min(1.0, max_y / h))

            extracted_boxes.append({
                "text": clean_text,
                "confidence": round(score_val, 4),
                "bbox": BoundingBox(x0=norm_x0, y0=norm_y0, x1=norm_x1, y1=norm_y1),
                "raw_polygon": dt_box,
                "pixel_bbox": [int(min_x), int(min_y), int(max_x), int(max_y)],
                "page_number": page_number,
                "source": "ocr"
            })

        return extracted_boxes


ocr_service = OCRService()
