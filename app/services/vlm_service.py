import base64
import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from openai import OpenAI
from app.config import settings
from app.core.logging import logger


class VLMService:
    """
    Vision-Language Model integration service.
    Provides targeted visual inspection of drawing crops and ambiguous callout regions.
    Safely falls back when no cloud API key is configured.
    """

    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.model = settings.LLM_MODEL
        self.api_key = settings.LLM_API_KEY or os.environ.get("OPENAI_API_KEY")
        self.enabled = settings.VLM_ENABLED and bool(self.api_key)

    def _encode_image_base64(self, image_path: Path) -> str:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def inspect_drawing_crop(
        self,
        crop_image_path: str | Path,
        context_prompt: str = "Analyze this mechanical drawing annotation. Identify nominal dimension, tolerance, and symbol."
    ) -> Dict[str, Any]:
        """
        Sends cropped drawing region to configured VLM API with structured output prompting.
        Returns candidate interpretation and confidence.
        """
        path = Path(crop_image_path)
        if not path.exists():
            return {
                "success": False,
                "error": f"Crop image path '{crop_image_path}' not found on disk."
            }

        if not self.enabled:
            # Deterministic heuristic fallback when cloud VLM API is not configured
            return {
                "success": True,
                "vlm_used": False,
                "provider": "local_heuristic",
                "notes": "VLM disabled or API key not configured; using deterministic fallback.",
                "candidate_interpretation": None,
                "confidence": 0.0
            }

        try:
            client = OpenAI(api_key=self.api_key, timeout=25.0)
            b64_img = self._encode_image_base64(path)

            system_instruction = (
                "You are an expert mechanical engineering drawing interpretation assistant. "
                "Analyze the provided drawing crop. Return a strict JSON object with fields: "
                "'dimension_type' (linear, diameter, radius, angular, thread, or other), "
                "'nominal_value' (number or null), "
                "'tolerance_type' (bilateral, asymmetric, limit, or none), "
                "'upper_deviation' (number or null), "
                "'lower_deviation' (number or null), "
                "'unit' (string or null), "
                "'feature_description' (string), "
                "'confidence' (0.0 to 1.0)."
            )

            response = client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_instruction},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": context_prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}"}}
                        ]
                    }
                ],
                max_tokens=300
            )

            raw_content = response.choices[0].message.content
            parsed = json.loads(raw_content)

            return {
                "success": True,
                "vlm_used": True,
                "provider": self.provider,
                "model": self.model,
                "candidate_interpretation": parsed,
                "confidence": float(parsed.get("confidence", 0.85))
            }
        except Exception as e:
            logger.warning(f"VLM call failed: {e}. Falling back safely.")
            return {
                "success": False,
                "vlm_used": False,
                "error": str(e),
                "confidence": 0.0
            }


vlm_service = VLMService()
