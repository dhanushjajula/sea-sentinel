"""
Candidate Verification Engine
Applies physics-grounded quality checks (acoustic contrast, shadow-highlight relief,
morphological solidity, geological rock clustering) to verify candidate debris objects
without aggressively destroying recall.
"""

from typing import Dict, Any, List, Optional, Tuple
import math
import cv2
import numpy as np


class CandidateVerifier:
    """
    Performs multi-factor verification on fused candidate objects.
    Preserves high recall by categorizing targets as 'confirmed' or 'suspicious'
    rather than discarding valid low-contrast targets.
    """
    def __init__(
        self,
        min_verification_score: float = 0.35,
        weights: Optional[Dict[str, float]] = None
    ):
        self.min_verification_score = min_verification_score
        self.weights = weights or {
            "contrast": 0.25,
            "shadow_relief": 0.25,
            "morphology_compactness": 0.20,
            "model_confidence": 0.30
        }

    def verify_candidates(
        self,
        candidates: List[Dict[str, Any]],
        image: np.ndarray,
        rock_filter_active: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Runs verification pipeline on all candidate objects.
        """
        if not candidates or image is None or image.size == 0:
            return candidates

        h, w = image.shape[:2]
        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        verified_objects = []

        for cand in candidates:
            rec = dict(cand)
            bbox = cand.get("bbox", {})
            x1 = max(0, min(w - 1, int(bbox.get("x1", 0))))
            y1 = max(0, min(h - 1, int(bbox.get("y1", 0))))
            x2 = max(x1 + 1, min(w, int(bbox.get("x2", w))))
            y2 = max(y1 + 1, min(h, int(bbox.get("y2", h))))

            patch = gray[y1:y2, x1:x2]

            # 1. Acoustic Contrast Score
            contrast_score = self._compute_contrast_score(gray, x1, y1, x2, y2)

            # 2. Acoustic Shadow-Highlight Relief Score
            shadow_score = self._compute_shadow_relief_score(gray, x1, y1, x2, y2)

            # 3. Morphology Score
            morph_score = self._compute_morphology_score(cand)

            # 4. Model Confidence Score
            conf = float(cand.get("confidence", 0.5))

            # Composite Verification Score
            w_c = self.weights.get("contrast", 0.25)
            w_s = self.weights.get("shadow_relief", 0.25)
            w_m = self.weights.get("morphology_compactness", 0.20)
            w_conf = self.weights.get("model_confidence", 0.30)

            v_score = (w_c * contrast_score) + (w_s * shadow_score) + (w_m * morph_score) + (w_conf * conf)
            
            # Dual-model agreement bonus
            if cand.get("source_category") == "BOTH":
                v_score = min(1.0, v_score + 0.12)

            # Check if flagged as rock cluster
            if cand.get("is_rock_cluster", False):
                v_score *= 0.65 # Down-weight but don't blindly delete

            v_score = round(float(v_score), 3)

            # Assign Status
            if v_score >= 0.65 or (cand.get("source_category") == "BOTH" and conf >= 0.60):
                status = "confirmed"
            elif v_score >= self.min_verification_score:
                status = "suspicious"
            else:
                status = "rejected"

            rec["verification_score"] = v_score
            rec["verification_status"] = status
            rec["quality_metrics"] = {
                "contrast_score": round(float(contrast_score), 3),
                "shadow_score": round(float(shadow_score), 3),
                "morphology_score": round(float(morph_score), 3)
            }
            verified_objects.append(rec)

        return verified_objects

    def _compute_contrast_score(self, gray: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> float:
        """Computes local contrast relative to the surrounding seabed background band."""
        h, w = gray.shape[:2]
        target_roi = gray[y1:y2, x1:x2]
        if target_roi.size == 0:
            return 0.5

        mean_tgt = float(np.mean(target_roi))

        # Define surrounding context ring (margin = 20% of bbox)
        bw = x2 - x1
        bh = y2 - y1
        pad_x = max(4, int(bw * 0.25))
        pad_y = max(4, int(bh * 0.25))

        ctx_x1 = max(0, x1 - pad_x)
        ctx_y1 = max(0, y1 - pad_y)
        ctx_x2 = min(w, x2 + pad_x)
        ctx_y2 = min(h, y2 + pad_y)

        context_roi = gray[ctx_y1:ctx_y2, ctx_x1:ctx_x2]
        mean_ctx = float(np.mean(context_roi)) if context_roi.size > 0 else 128.0

        diff = abs(mean_tgt - mean_ctx)
        # Higher difference indicates distinct acoustic reflectivity
        contrast_score = min(1.0, max(0.1, diff / 60.0))
        return contrast_score

    def _compute_shadow_relief_score(self, gray: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> float:
        """Evaluates whether an acoustic shadow void exists near the target highlight."""
        h, w = gray.shape[:2]
        bw = x2 - x1
        bh = y2 - y1

        # Look in trailing direction (downward or outward from nadir)
        shadow_y1 = min(h - 1, y2)
        shadow_y2 = min(h, y2 + int(bh * 1.5) + 5)
        if shadow_y2 > shadow_y1:
            shadow_band = gray[shadow_y1:shadow_y2, x1:x2]
            if shadow_band.size > 0:
                min_shadow = float(np.min(shadow_band))
                mean_shadow = float(np.mean(shadow_band))
                if min_shadow < 35 or mean_shadow < 60:
                    return 0.85
                elif mean_shadow < 90:
                    return 0.65
        return 0.45

    def _compute_morphology_score(self, cand: Dict[str, Any]) -> float:
        """Evaluates aspect ratio, compactness, and solidity."""
        aspect_ratio = float(cand.get("aspect_ratio", 1.0))
        compactness = cand.get("compactness")
        solidity = cand.get("solidity")

        score = 0.5
        # Elongated targets (cables/pipelines) or compact objects (engines/containers)
        if aspect_ratio >= 2.0 or aspect_ratio <= 1.3:
            score += 0.15

        if compactness is not None and compactness > 0.3:
            score += 0.15

        if solidity is not None and solidity > 0.4:
            score += 0.15

        return min(1.0, max(0.2, score))
