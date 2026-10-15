import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Optional
from PIL import Image
from app.config import settings


class PreprocessingService:
    """Image preprocessing utilities for engineering drawing OCR and feature detection."""

    @staticmethod
    def load_image(image_input: str | Path | bytes | np.ndarray) -> np.ndarray:
        if isinstance(image_input, np.ndarray):
            return image_input
        if isinstance(image_input, (str, Path)):
            img = cv2.imread(str(image_input))
            if img is None:
                raise ValueError(f"Could not load image from {image_input}")
            return img
        if isinstance(image_input, bytes):
            nparr = np.frombuffer(image_input, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("Could not decode image from byte buffer")
            return img
        raise TypeError(f"Unsupported image input type: {type(image_input)}")

    def enhance_for_ocr(self, img: np.ndarray) -> np.ndarray:
        """
        Enhances document image for high-accuracy OCR:
        - Converts to grayscale
        - Applies Contrast Limited Adaptive Histogram Equalization (CLAHE)
        - Denoises gently to retain thin dimension lines
        """
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()

        # CLAHE for contrast enhancement in low-contrast scans
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        return enhanced

    def deskew(self, img: np.ndarray, max_angle: float = 10.0) -> Tuple[np.ndarray, float]:
        """
        Detects skew angle and rotates image if skew is below max_angle.
        Returns (deskewed_image, detected_angle).
        """
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img

        # Threshold inverted image
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
        coords = np.column_stack(np.where(thresh > 0))
        if len(coords) < 50:
            return img, 0.0

        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        if abs(angle) > max_angle or abs(angle) < 0.2:
            return img, 0.0

        (h, w) = img.shape[:2]
        center = (w // 2, h // 2)
        m = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        return rotated, angle

    def crop_normalized_bbox(
        self,
        img: np.ndarray,
        bbox_x0: float,
        bbox_y0: float,
        bbox_x1: float,
        bbox_y1: float,
        padding_ratio: float = 0.05
    ) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
        """
        Crops a region given normalized coordinates (0.0 to 1.0) with optional margin padding.
        Returns (cropped_image, (px0, py0, px1, py1)).
        """
        h, w = img.shape[:2]
        pad_x = int((bbox_x1 - bbox_x0) * w * padding_ratio)
        pad_y = int((bbox_y1 - bbox_y0) * h * padding_ratio)

        px0 = max(0, int(bbox_x0 * w) - pad_x)
        py0 = max(0, int(bbox_y0 * h) - pad_y)
        px1 = min(w, int(bbox_x1 * w) + pad_x)
        py1 = min(h, int(bbox_y1 * h) + pad_y)

        if px1 <= px0 or py1 <= py0:
            return img, (0, 0, w, h)

        return img[py0:py1, px0:px1], (px0, py0, px1, py1)


preprocessing_service = PreprocessingService()
