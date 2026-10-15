import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.services.preprocessing_service import preprocessing_service


class DrawingGeometryService:
    """
    Detects geometric primitives (circles, arcs, linear boundaries, slots) from:
    1. Rendered raster drawing images (via Hough transforms and contour analysis)
    2. Vector graphics streams extracted from vector PDFs
    """

    def detect_features_from_image(self, image_input: str | Path | np.ndarray) -> List[Dict[str, Any]]:
        img = preprocessing_service.load_image(image_input)
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

        features = []

        # 1. Circle & Arc Detection using HoughCircles
        # Blur to reduce false positives
        blurred = cv2.GaussianBlur(gray, (9, 9), 2)
        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=int(min(w, h) * 0.05),
            param1=80,
            param2=35,
            minRadius=int(min(w, h) * 0.015),
            maxRadius=int(min(w, h) * 0.40)
        )

        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")
            for idx, (cx, cy, r) in enumerate(circles):
                if 0 <= cx < w and 0 <= cy < h and r > 0:
                    norm_cx = cx / w
                    norm_cy = cy / h
                    norm_r = r / min(w, h)

                    norm_x0 = max(0.0, (cx - r) / w)
                    norm_y0 = max(0.0, (cy - r) / h)
                    norm_x1 = min(1.0, (cx + r) / w)
                    norm_y1 = min(1.0, (cy + r) / h)

                    features.append({
                        "feature_type": "circle",
                        "center_x": norm_cx,
                        "center_y": norm_cy,
                        "radius": norm_r,
                        "pixel_radius": int(r),
                        "bbox_x0": norm_x0,
                        "bbox_y0": norm_y0,
                        "bbox_x1": norm_x1,
                        "bbox_y1": norm_y1,
                        "evidence": f"Hough circle detected at center ({cx}, {cy}) with radius {r}px"
                    })

        # 2. Linear Boundary Detection using Probabilistic Hough Lines
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=50,
            minLineLength=int(min(w, h) * 0.05),
            maxLineGap=10
        )

        if lines is not None:
            for idx, l in enumerate(lines[:20]):  # cap to top salient linear features
                line_pts = l[0] if hasattr(l, "ndim") and l.ndim > 1 else l
                if len(line_pts) == 4:
                    x1, y1, x2, y2 = [int(v) for v in line_pts]
                    norm_x0 = min(x1, x2) / w
                    norm_y0 = min(y1, y2) / h
                    norm_x1 = max(x1, x2) / w
                    norm_y1 = max(y1, y2) / h
                    length_px = float(np.hypot(x2 - x1, y2 - y1))

                    features.append({
                        "feature_type": "line",
                        "center_x": ((x1 + x2) / 2) / w,
                        "center_y": ((y1 + y2) / 2) / h,
                        "radius": None,
                        "bbox_x0": norm_x0,
                        "bbox_y0": norm_y0,
                        "bbox_x1": norm_x1,
                        "bbox_y1": norm_y1,
                        "evidence": f"Line segment detected from ({x1},{y1}) to ({x2},{y2}), length {int(length_px)}px"
                    })

        return features


drawing_geometry_service = DrawingGeometryService()
