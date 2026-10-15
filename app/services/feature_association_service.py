import math
from typing import List, Dict, Any, Optional, Tuple
from app.schemas.annotation import NormalizedDimension


class FeatureAssociationService:
    """
    Associates dimension annotations with geometric drawing features (circles, lines, slots).
    Evaluates geometric proximity, dimension-type compatibility, and directional alignment.
    Enforces ambiguity detection: records with competing candidates are routed to human review.
    """

    def associate_annotations_with_features(
        self,
        annotations: List[NormalizedDimension],
        features: List[Dict[str, Any]],
        max_association_distance: float = 0.35
    ) -> List[Dict[str, Any]]:
        """
        Calculates association candidates for each annotation.
        Returns a list of proposed associations with candidate features and ambiguity status.
        """
        associations = []

        for ann_idx, ann in enumerate(annotations):
            ann_cx = (ann.bbox.x0 + ann.bbox.x1) / 2.0
            ann_cy = (ann.bbox.y0 + ann.bbox.y1) / 2.0

            scored_candidates = []

            for feat_idx, feat in enumerate(features):
                fcx = feat.get("center_x") or ((feat["bbox_x0"] + feat["bbox_x1"]) / 2.0)
                fcy = feat.get("center_y") or ((feat["bbox_y0"] + feat["bbox_y1"]) / 2.0)

                # Euclidean distance in normalized coordinate space
                dist = math.hypot(ann_cx - fcx, ann_cy - fcy)
                if dist > max_association_distance:
                    continue

                # Type compatibility score
                compat_score = 0.5
                feat_type = feat.get("feature_type", "unknown")

                if ann.dimension_type in ("diameter", "radius"):
                    if feat_type in ("circle", "arc", "arc_or_circle"):
                        compat_score = 1.0
                    else:
                        compat_score = 0.2  # diameter on straight line is questionable
                elif ann.dimension_type == "linear":
                    if feat_type in ("line", "rectangle", "boundary"):
                        compat_score = 0.9
                    else:
                        compat_score = 0.4
                elif ann.dimension_type == "thread":
                    if feat_type in ("circle", "arc", "arc_or_circle"):
                        compat_score = 0.95
                    else:
                        compat_score = 0.3

                # Proximity score (1.0 = identical coordinates, 0.0 = max distance)
                prox_score = max(0.0, 1.0 - (dist / max_association_distance))

                # Combined confidence
                candidate_confidence = round((prox_score * 0.6) + (compat_score * 0.4), 4)

                scored_candidates.append({
                    "feature_index": feat_idx,
                    "feature": feat,
                    "distance": round(dist, 4),
                    "confidence": candidate_confidence,
                    "method": f"geometric_{feat_type}_proximity"
                })

            # Sort by descending confidence
            scored_candidates.sort(key=lambda x: x["confidence"], reverse=True)

            if not scored_candidates:
                # No feature within proximity
                associations.append({
                    "annotation_index": ann_idx,
                    "annotation": ann,
                    "feature_index": None,
                    "feature": None,
                    "association_method": "unassociated",
                    "confidence": 0.0,
                    "is_ambiguous": True,
                    "ambiguity_reason": "No plausible geometric feature detected within proximity limit.",
                    "review_status": "pending_review"
                })
                continue

            top_candidate = scored_candidates[0]
            is_ambiguous = False
            ambiguity_reason = None

            # Check if second candidate is dangerously close in score
            if len(scored_candidates) > 1:
                second = scored_candidates[1]
                if (top_candidate["confidence"] - second["confidence"]) < 0.12:
                    is_ambiguous = True
                    ambiguity_reason = (
                        f"Ambiguous feature association: multiple candidate features with similar scores "
                        f"({top_candidate['confidence']:.2f} vs {second['confidence']:.2f})."
                    )

            if top_candidate["confidence"] < 0.55:
                is_ambiguous = True
                ambiguity_reason = f"Low association confidence ({top_candidate['confidence']:.2f})."

            associations.append({
                "annotation_index": ann_idx,
                "annotation": ann,
                "feature_index": top_candidate["feature_index"],
                "feature": top_candidate["feature"],
                "association_method": top_candidate["method"],
                "confidence": top_candidate["confidence"],
                "is_ambiguous": is_ambiguous,
                "ambiguity_reason": ambiguity_reason,
                "candidate_count": len(scored_candidates),
                "review_status": "pending_review" if is_ambiguous else "approved"
            })

        return associations


feature_association_service = FeatureAssociationService()
