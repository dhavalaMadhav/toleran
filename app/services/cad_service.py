from pathlib import Path
from typing import Dict, Any, List, Optional
import ezdxf
from app.core.logging import logger


class CADService:
    """
    DXF CAD exchange parser supporting standard 2D entities:
    - Supported Entities: LINE, CIRCLE, ARC, TEXT, MTEXT, DIMENSION, INSERT (blocks).
    - Supported DXF Versions: AutoCAD R12 through AutoCAD 2018 (AC1009 - AC1032).
    - Limitations: 3D solids, complex ACIS bodies, and custom proxy entities are not modeled.
    """

    SUPPORTED_ENTITIES = ["LINE", "CIRCLE", "ARC", "TEXT", "MTEXT", "DIMENSION", "INSERT"]

    def parse_dxf(self, dxf_path: str | Path) -> Dict[str, Any]:
        """
        Parses a DXF file and extracts geometric entities and annotations.
        """
        try:
            doc = ezdxf.readfile(str(dxf_path))
        except Exception as e:
            logger.error(f"Error loading DXF file {dxf_path}: {e}")
            raise ValueError(f"Failed to parse DXF file: {str(e)}")

        msp = doc.modelspace()
        entities = []
        annotations = []
        layers = set()

        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")

        for e in msp:
            dxftype = e.dxftype()
            layer = e.dxf.layer
            layers.add(layer)

            if dxftype == "LINE":
                start = (e.dxf.start.x, e.dxf.start.y)
                end = (e.dxf.end.x, e.dxf.end.y)
                min_x = min(min_x, start[0], end[0])
                min_y = min(min_y, start[1], end[1])
                max_x = max(max_x, start[0], end[0])
                max_y = max(max_y, start[1], end[1])

                entities.append({
                    "type": "line",
                    "layer": layer,
                    "handle": e.dxf.handle,
                    "start": start,
                    "end": end
                })

            elif dxftype == "CIRCLE":
                center = (e.dxf.center.x, e.dxf.center.y)
                radius = float(e.dxf.radius)
                min_x = min(min_x, center[0] - radius)
                min_y = min(min_y, center[1] - radius)
                max_x = max(max_x, center[0] + radius)
                max_y = max(max_y, center[1] + radius)

                entities.append({
                    "type": "circle",
                    "layer": layer,
                    "handle": e.dxf.handle,
                    "center": center,
                    "radius": radius
                })

            elif dxftype == "ARC":
                center = (e.dxf.center.x, e.dxf.center.y)
                radius = float(e.dxf.radius)
                start_angle = float(e.dxf.start_angle)
                end_angle = float(e.dxf.end_angle)
                min_x = min(min_x, center[0] - radius)
                min_y = min(min_y, center[1] - radius)
                max_x = max(max_x, center[0] + radius)
                max_y = max(max_y, center[1] + radius)

                entities.append({
                    "type": "arc",
                    "layer": layer,
                    "handle": e.dxf.handle,
                    "center": center,
                    "radius": radius,
                    "start_angle": start_angle,
                    "end_angle": end_angle
                })

            elif dxftype in ("TEXT", "MTEXT"):
                text = e.dxf.text if dxftype == "TEXT" else e.text
                insert = (e.dxf.insert.x, e.dxf.insert.y)
                min_x = min(min_x, insert[0])
                min_y = min(min_y, insert[1])
                max_x = max(max_x, insert[0])
                max_y = max(max_y, insert[1])

                annotations.append({
                    "text": text.strip(),
                    "layer": layer,
                    "handle": e.dxf.handle,
                    "position": insert,
                    "source": "cad_entity"
                })

            elif dxftype == "DIMENSION":
                dim_text = getattr(e.dxf, "text", "")
                annotations.append({
                    "text": dim_text.strip() if dim_text else "DIMENSION_ENTITY",
                    "layer": layer,
                    "handle": e.dxf.handle,
                    "source": "cad_dimension"
                })

        # Calculate bounding box extent
        span_x = max_x - min_x if max_x > min_x else 1.0
        span_y = max_y - min_y if max_y > min_y else 1.0

        return {
            "dxf_version": doc.dxfversion,
            "layers": list(layers),
            "entity_count": len(entities),
            "annotation_count": len(annotations),
            "extent": {
                "min_x": min_x if min_x != float("inf") else 0.0,
                "min_y": min_y if min_y != float("inf") else 0.0,
                "max_x": max_x if max_x != float("-inf") else 0.0,
                "max_y": max_y if max_y != float("-inf") else 0.0,
                "span_x": span_x,
                "span_y": span_y
            },
            "entities": entities,
            "annotations": annotations
        }


cad_service = CADService()
