"""
Review Intelligence Engine for Sea Sentinel Adaptive Learning.
Analyzes human verifier corrections, extracts exact failure modes, classifies error types,
and converts reviews into machine-readable training directives and structured error records.
"""

from typing import Dict, Any, List, Optional, Tuple
import os
import re
import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class StructuredErrorRecord(BaseModel):
    review_id: str
    image_id: str
    prediction_id: str
    model_name: str = "YOLO+UNET"
    model_version: str = "v3.2"
    predicted_class: str
    correct_class: str
    predicted_confidence: float = 0.85
    error_category: str = "DETECTION"
    error_type: str = "FALSE_POSITIVE"
    training_action: str = "HARD_NEGATIVE"
    is_unknown_object: bool = False
    candidate_class_name: Optional[str] = None
    bbox_correction: Optional[Dict[str, float]] = None
    segmentation_correction: Optional[List[List[float]]] = None
    human_comment: str = ""
    extracted_reason: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    dataset_version: str = "v1.0"
    spatial_metadata: Optional[Dict[str, Any]] = None


class ReviewIntelligenceEngine:
    """
    Translates raw human feedback and structured annotations into actionable machine learning directives.
    """

    KNOWN_CLASSES = [
        "fishing_net", "ghost_net", "pipeline_or_cable", "shipwreck_fragment",
        "engine_debris", "riprap_debris", "metal_container", "tire", "plastic_debris"
    ]

    CLASS_MAPPINGS = {
        "net": "fishing_net",
        "ghost net": "fishing_net",
        "fishing net": "fishing_net",
        "cable": "pipeline_or_cable",
        "pipe": "pipeline_or_cable",
        "pipeline": "pipeline_or_cable",
        "wreck": "shipwreck_fragment",
        "shipwreck": "shipwreck_fragment",
        "engine": "engine_debris",
        "motor": "engine_debris",
        "rock": "riprap_debris",
        "boulder": "riprap_debris",
        "stone": "riprap_debris",
        "seabed": "background",
        "background": "background",
        "ridge": "background",
        "sand": "background",
        "tire": "tire",
        "tyre": "tire",
        "container": "metal_container",
        "barrel": "metal_container"
    }

    def analyze_review(
        self,
        image_id: str,
        prediction_id: str,
        predicted_class: str,
        predicted_confidence: float,
        review_type: Optional[str] = None,
        corrected_class: Optional[str] = None,
        human_comment: str = "",
        bbox_correction: Optional[Dict[str, float]] = None,
        polygon_correction: Optional[List[List[float]]] = None,
        is_unknown: bool = False,
        candidate_class_name: Optional[str] = None,
        model_name: str = "YOLO+UNET",
        model_version: str = "v3.2",
        spatial_meta: Optional[Dict[str, Any]] = None
    ) -> StructuredErrorRecord:
        """
        Parses structured review attributes and NLU commentary to synthesize a StructuredErrorRecord.
        """
        review_id = f"REV_{uuid.uuid4().hex[:8].upper()}"
        cleaned_pred = (predicted_class or "unknown").lower().replace(" ", "_")

        # 1. Normalize Review Type & Error Categorization
        error_type, error_category, training_action, target_class = self._determine_error_classification(
            review_type=review_type,
            predicted_class=cleaned_pred,
            corrected_class=corrected_class,
            human_comment=human_comment,
            is_unknown=is_unknown
        )

        extracted_reason = self._synthesize_reason(error_type, cleaned_pred, target_class, human_comment)

        return StructuredErrorRecord(
            review_id=review_id,
            image_id=image_id,
            prediction_id=prediction_id,
            model_name=model_name,
            model_version=model_version,
            predicted_class=cleaned_pred,
            correct_class=target_class,
            predicted_confidence=round(predicted_confidence, 3),
            error_category=error_category,
            error_type=error_type,
            training_action=training_action,
            is_unknown_object=is_unknown or error_type == "UNKNOWN_OBJECT",
            candidate_class_name=target_class if (is_unknown or error_type == "UNKNOWN_OBJECT") else None,
            bbox_correction=bbox_correction,
            segmentation_correction=polygon_correction,
            human_comment=human_comment,
            extracted_reason=extracted_reason,
            timestamp=datetime.utcnow().isoformat(),
            dataset_version="v1.0",
            spatial_metadata=spatial_meta
        )

    def _determine_error_classification(
        self,
        review_type: Optional[str],
        predicted_class: str,
        corrected_class: Optional[str],
        human_comment: str,
        is_unknown: bool
    ) -> Tuple[str, str, str, str]:
        """
        Infers exact (error_type, error_category, training_action, correct_class).
        """
        comment_lower = human_comment.lower().strip()
        review_norm = (review_type or "").upper().replace(" ", "_")

        # Check explicit unknown object
        if is_unknown or review_norm in ("UNKNOWN_OBJECT", "CANDIDATE_NEW_CLASS"):
            cand = corrected_class or self._extract_candidate_class_name(comment_lower) or "unknown_marine_artifact"
            return "UNKNOWN_OBJECT", "UNKNOWN", "NEW_CLASS_CANDIDATE", cand

        # A. Explicit Review Type Handling
        if review_norm == "CORRECT":
            return "NO_ERROR", "CORRECT", "STANDARD_POSITIVE", predicted_class

        if review_norm in ("FALSE_POSITIVE", "FALSE_ALARM"):
            target_cls = corrected_class or self._extract_class_from_text(comment_lower) or "background"
            action = "HARD_NEGATIVE" if target_cls in ("background", "seabed_texture", "rock", "sand_ripple", "seabed") else "RECLASSIFICATION"
            return "FALSE_POSITIVE", "DETECTION", action, target_cls

        if review_norm in ("FALSE_NEGATIVE", "MISSED_OBJECT"):
            target_cls = corrected_class or self._extract_class_from_text(comment_lower) or "fishing_net"
            return "FALSE_NEGATIVE", "DETECTION", "MISSED_TARGET_INJECTION", target_cls

        if review_norm in ("WRONG_CLASS", "WRONG_CLASSIFICATION", "CONFUSED_CLASS"):
            target_cls = corrected_class or self._extract_class_from_text(comment_lower) or "riprap_debris"
            return "WRONG_CLASS", "CLASSIFICATION", "RECLASSIFICATION", target_cls

        if review_norm in ("POOR_BBOX", "WRONG_BOUNDING_BOX", "LOCALIZATION_ERROR"):
            return "POOR_BBOX", "DETECTION", "BOUNDING_BOX_REFINEMENT", predicted_class

        if review_norm in ("INCORRECT_MASK", "INCOMPLETE_MASK", "EXCESSIVE_MASK", "BOUNDARY_ERROR"):
            return "INCORRECT_MASK", "SEGMENTATION", "MASK_REFINEMENT", predicted_class

        if review_norm == "DUPLICATE_DETECTION":
            return "DUPLICATE_DETECTION", "DETECTION", "NMS_CALIBRATION", predicted_class

        # B. Fallback Natural Language Analysis
        if any(neg in comment_lower for neg in ["not a", "false alarm", "seabed texture", "just sand", "natural ridge", "empty"]):
            target_cls = self._extract_class_from_text(comment_lower) or "background"
            return "FALSE_POSITIVE", "DETECTION", "HARD_NEGATIVE", target_cls

        if any(miss in comment_lower for miss in ["missed", "overlooked", "not detected", "did not see"]):
            target_cls = self._extract_class_from_text(comment_lower) or "fishing_net"
            return "FALSE_NEGATIVE", "DETECTION", "MISSED_TARGET_INJECTION", target_cls

        if any(kw in comment_lower for kw in ["actually a", "is a rock", "is a pipeline", "is a net", "confused with", "wrong class"]):
            target_cls = self._extract_class_from_text(comment_lower) or "riprap_debris"
            return "WRONG_CLASS", "CLASSIFICATION", "RECLASSIFICATION", target_cls

        # Default fallback
        target_cls = corrected_class or (predicted_class if predicted_class != "unknown" else "fishing_net")
        return "FALSE_POSITIVE", "DETECTION", "HARD_NEGATIVE", target_cls

    def _extract_class_from_text(self, text: str) -> Optional[str]:
        for key, val in self.CLASS_MAPPINGS.items():
            pattern = rf"\b{re.escape(key)}\b"
            if re.search(pattern, text):
                return val
        return None

    def _extract_candidate_class_name(self, text: str) -> Optional[str]:
        match = re.search(r"(?:called|named|identified as|is a|type of)\s+([a-zA-Z0-9_\-\s]{3,24})", text)
        if match:
            cand = match.group(1).strip().replace(" ", "_").lower()
            return cand
        return None

    @staticmethod
    def _synthesize_reason(error_type: str, pred_class: str, target_class: str, comment: str) -> str:
        if comment:
            return f"{error_type}: {comment}"
        if error_type == "FALSE_POSITIVE":
            return f"Acoustic artifact or {target_class} incorrectly detected as {pred_class}."
        if error_type == "WRONG_CLASS":
            return f"Class confusion between {pred_class} and true class {target_class}."
        if error_type == "FALSE_NEGATIVE":
            return f"Model failed to detect valid benthic target of class {target_class}."
        if error_type == "UNKNOWN_OBJECT":
            return f"Unidentified acoustic structure proposed as new candidate class '{target_class}'."
        return f"Human review verification completed ({error_type})."
