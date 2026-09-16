"""
Active Learning Engine for Sea Sentinel.
Prioritizes uncertain detections, model disagreements, unknown objects,
and visual patterns matching historical failure modes for human verification.
"""

from typing import Dict, Any, List, Optional
import os
import sqlite3
import json
import uuid
from datetime import datetime
from .error_memory import ErrorMemoryEngine

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DB_PATH = os.path.join(PROJECT_ROOT, "outputs", "database", "sea_sentinel_edge.db")


class ActiveLearningEngine:
    """
    Intelligently scores and filters sonar inferences into a prioritized Active Learning human review queue.
    """

    def __init__(self, error_memory: Optional[ErrorMemoryEngine] = None, db_path: str = DB_PATH):
        self.error_memory = error_memory or ErrorMemoryEngine()
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_schema(self):
        with self._get_connection() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS active_learning_queue (
                item_id TEXT PRIMARY KEY,
                image_id TEXT,
                object_id TEXT,
                predicted_class TEXT,
                confidence REAL,
                source_category TEXT,
                uncertainty_score REAL,
                priority_reason TEXT,
                bbox_json TEXT,
                crop_path TEXT,
                status TEXT DEFAULT 'PENDING_REVIEW',
                enqueued_at TEXT
            );
            """)
            conn.commit()

    def evaluate_detection_for_review(
        self,
        image_id: str,
        detection: Dict[str, Any],
        crop_image: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Calculates uncertainty score and enqueues candidate if active learning criteria are met.
        """
        conf = float(detection.get("calibrated_confidence", detection.get("confidence", 0.85)))
        src_cat = detection.get("source_category", "BOTH")
        poly = detection.get("polygon", [])
        is_unknown = detection.get("is_unknown_object", False)
        bbox = detection.get("pixel_bbox", detection.get("bbox", {}))
        obj_id = detection.get("object_id", "OBJ")

        reasons = []
        uncertainty = 0.0

        # 1. Low Model Confidence
        if conf < 0.50:
            uncertainty += 0.50
            reasons.append(f"Low AI confidence ({int(conf * 100)}%)")
        elif conf < 0.70:
            uncertainty += 0.25

        # 2. Inter-Model Disagreement
        if src_cat != "BOTH":
            uncertainty += 0.50
            reasons.append(f"Single-model candidate ({src_cat})")

        # 3. Small Object Extent
        bw = abs(float(bbox.get("x2", 0)) - float(bbox.get("x1", 0)))
        bh = abs(float(bbox.get("y2", 0)) - float(bbox.get("y1", 0)))
        if bw * bh < 400.0:  # <20x20 px
            uncertainty += 0.25
            reasons.append("Small acoustic footprint (<20px)")

        # 4. Unknown Object Flag
        if is_unknown or detection.get("class") in ("unknown", "unclassified_debris"):
            uncertainty += 0.50
            reasons.append("Unknown or unclassified acoustic morphology")

        # 5. Visual Similarity to Historical Failure
        if crop_image is not None and hasattr(crop_image, "size") and crop_image.size > 0:
            similar_errors = self.error_memory.search_similar_errors(crop_image, threshold=0.82, top_k=1)
            if similar_errors:
                top_err = similar_errors[0]
                uncertainty += 0.45
                reasons.append(f"Matches historical failure ERR: {top_err.get('predicted_class')}->{top_err.get('correct_class')} ({int(top_err.get('similarity', 0.8)*100)}% match)")

        uncertainty = min(1.0, uncertainty)
        needs_review = (uncertainty >= 0.45)

        if needs_review:
            item_id = f"AL_{uuid.uuid4().hex[:8].upper()}"
            with self._get_connection() as conn:
                conn.execute("""
                INSERT OR REPLACE INTO active_learning_queue (
                    item_id, image_id, object_id, predicted_class, confidence,
                    source_category, uncertainty_score, priority_reason, bbox_json, status, enqueued_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING_REVIEW', ?)
                """, (
                    item_id, image_id, obj_id, detection.get("class", "debris"),
                    conf, src_cat, round(uncertainty, 3), "; ".join(reasons),
                    json.dumps(bbox), datetime.utcnow().isoformat()
                ))
                conn.commit()

        return {
            "needs_human_review": needs_review,
            "uncertainty_score": round(uncertainty, 3),
            "priority_reasons": reasons
        }

    def get_pending_queue(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute("""
            SELECT item_id, image_id, object_id, predicted_class, confidence, 
                   source_category, uncertainty_score, priority_reason, bbox_json, status, enqueued_at 
            FROM active_learning_queue 
            WHERE status = 'PENDING_REVIEW' 
            ORDER BY uncertainty_score DESC LIMIT ?
            """, (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def resolve_queue_item(self, item_id: str, status: str = "RESOLVED"):
        with self._get_connection() as conn:
            conn.execute("UPDATE active_learning_queue SET status = ? WHERE item_id = ?", (status, item_id))
            conn.commit()
