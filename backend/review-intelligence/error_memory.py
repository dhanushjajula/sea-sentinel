"""
Persistent Error Memory & Recurring Mistake Engine for Sea Sentinel.
Stores verified prediction failures, calculates recurring error patterns,
extracts invariant acoustic embeddings, and powers regression test suites.
"""

from typing import Dict, Any, List, Optional, Tuple
import os
import json
import sqlite3
import numpy as np
import cv2
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DB_DIR = os.path.join(PROJECT_ROOT, "outputs", "database")
DB_PATH = os.path.join(DB_DIR, "sea_sentinel_edge.db")
CROPS_DIR = os.path.join(PROJECT_ROOT, "outputs", "learning", "error_crops")
os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(CROPS_DIR, exist_ok=True)


class ErrorMemoryEngine:
    """
    Persistent Error Memory repository indexing acoustic visual signatures and tracking recurring mistakes.
    """

    def __init__(self, db_path: str = DB_PATH):
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
            CREATE TABLE IF NOT EXISTS error_memory (
                error_id TEXT PRIMARY KEY,
                review_id TEXT,
                image_id TEXT,
                prediction_id TEXT,
                model_name TEXT,
                model_version TEXT,
                predicted_class TEXT,
                correct_class TEXT,
                predicted_confidence REAL,
                error_category TEXT,
                error_type TEXT,
                training_action TEXT,
                crop_path TEXT,
                feature_vector_json TEXT,
                is_unknown_object INTEGER DEFAULT 0,
                status TEXT DEFAULT 'PENDING_RETRAINING',
                regression_status TEXT DEFAULT 'ACTIVE_TEST',
                recurrence_count INTEGER DEFAULT 1,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS recurring_error_patterns (
                pattern_id TEXT PRIMARY KEY,
                predicted_class TEXT,
                correct_class TEXT,
                error_type TEXT,
                total_occurrences INTEGER DEFAULT 1,
                last_seen_at TEXT
            );

            CREATE TABLE IF NOT EXISTS regression_test_suite (
                test_id TEXT PRIMARY KEY,
                error_id TEXT,
                sample_image_path TEXT,
                expected_outcome TEXT,
                forbidden_outcome TEXT,
                last_champion_result TEXT,
                last_challenger_result TEXT,
                test_status TEXT DEFAULT 'PENDING'
            );
            """)
            conn.commit()

    @staticmethod
    def extract_visual_embedding(crop: np.ndarray) -> List[float]:
        """Extracts normalized 32-dim acoustic invariant descriptor."""
        if crop is None or crop.size == 0:
            return [0.0] * 32
        if len(crop.shape) == 3:
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        else:
            gray = crop.copy()

        hist = cv2.calcHist([gray], [0], None, [16], [0, 256]).flatten()
        hist_norm = hist / (hist.sum() + 1e-7)

        moments = cv2.moments(gray)
        hu = cv2.HuMoments(moments).flatten()
        hu_log = -np.sign(hu) * np.log10(np.abs(hu) + 1e-12)

        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        grad_mag = np.sqrt(gx**2 + gy**2)
        g_mean = float(np.mean(grad_mag))
        g_std = float(np.std(grad_mag))

        h, w = gray.shape[:2]
        aspect = float(w) / max(1.0, float(h))
        density = float(np.count_nonzero(gray > 30)) / max(1.0, float(h * w))

        vec = np.concatenate([
            hist_norm[:16],
            hu_log[:7],
            [g_mean / 255.0, g_std / 255.0, min(aspect / 5.0, 1.0), density]
        ])
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return [round(float(v), 5) for v in vec[:32]]

    def record_error(
        self,
        record: Any,
        crop_image: Optional[np.ndarray] = None
    ) -> str:
        """Stores structured error record, updates pattern recurrence, and saves visual crop."""
        err_id = f"ERR_{record.review_id.replace('REV_', '')}"
        crop_path = ""
        embedding = [0.0] * 32

        if crop_image is not None and crop_image.size > 0:
            crop_fname = f"{err_id}_{record.predicted_class}_to_{record.correct_class}.png"
            crop_path = os.path.join(CROPS_DIR, crop_fname)
            try:
                cv2.imwrite(crop_path, crop_image)
                embedding = self.extract_visual_embedding(crop_image)
            except Exception:
                pass

        pattern_key = f"{record.predicted_class}_TO_{record.correct_class}".upper()

        with self._get_connection() as conn:
            # 1. Insert Error Record
            conn.execute("""
            INSERT OR REPLACE INTO error_memory (
                error_id, review_id, image_id, prediction_id, model_name, model_version,
                predicted_class, correct_class, predicted_confidence, error_category, error_type,
                training_action, crop_path, feature_vector_json, is_unknown_object, status,
                regression_status, recurrence_count, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING_RETRAINING', 'ACTIVE_TEST', 1, ?)
            """, (
                err_id, record.review_id, record.image_id, record.prediction_id,
                record.model_name, record.model_version, record.predicted_class,
                record.correct_class, record.predicted_confidence, record.error_category,
                record.error_type, record.training_action, crop_path, json.dumps(embedding),
                1 if record.is_unknown_object else 0, record.timestamp
            ))

            # 2. Update Recurring Pattern Counter
            cur_pat = conn.execute("SELECT total_occurrences FROM recurring_error_patterns WHERE pattern_id = ?", (pattern_key,)).fetchone()
            if cur_pat:
                new_cnt = cur_pat["total_occurrences"] + 1
                conn.execute("""
                UPDATE recurring_error_patterns 
                SET total_occurrences = ?, last_seen_at = ? 
                WHERE pattern_id = ?
                """, (new_cnt, record.timestamp, pattern_key))
            else:
                conn.execute("""
                INSERT INTO recurring_error_patterns (pattern_id, predicted_class, correct_class, error_type, total_occurrences, last_seen_at)
                VALUES (?, ?, ?, ?, 1, ?)
                """, (pattern_key, record.predicted_class, record.correct_class, record.error_type, record.timestamp))

            # 3. Register into Regression Test Suite
            test_id = f"REG_{err_id}"
            conn.execute("""
            INSERT OR REPLACE INTO regression_test_suite (
                test_id, error_id, sample_image_path, expected_outcome, forbidden_outcome, test_status
            ) VALUES (?, ?, ?, ?, ?, 'ACTIVE')
            """, (test_id, err_id, crop_path, record.correct_class, record.predicted_class))

            conn.commit()

        return err_id

    def search_similar_errors(
        self,
        query_crop: np.ndarray,
        threshold: float = 0.80,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Finds historical mistakes matching the visual acoustic pattern of a query detection."""
        query_vec = np.array(self.extract_visual_embedding(query_crop), dtype=np.float32)
        if np.linalg.norm(query_vec) == 0:
            return []

        matches = []
        with self._get_connection() as conn:
            cursor = conn.execute("""
            SELECT error_id, predicted_class, correct_class, error_type, predicted_confidence, 
                   feature_vector_json, crop_path, recurrence_count 
            FROM error_memory WHERE crop_path != '' LIMIT 200
            """)
            for row in cursor.fetchall():
                try:
                    feat = np.array(json.loads(row["feature_vector_json"]), dtype=np.float32)
                    if feat.shape == query_vec.shape:
                        sim = float(np.dot(query_vec, feat))
                        if sim >= threshold:
                            d = dict(row)
                            d["similarity"] = round(sim, 3)
                            matches.append(d)
                except Exception:
                    continue

        matches.sort(key=lambda x: x["similarity"], reverse=True)
        return matches[:top_k]

    def get_recurring_error_matrix(self) -> List[Dict[str, Any]]:
        """Returns list of top recurring failure patterns sorted by frequency."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
            SELECT pattern_id, predicted_class, correct_class, error_type, total_occurrences, last_seen_at 
            FROM recurring_error_patterns 
            ORDER BY total_occurrences DESC LIMIT 15
            """)
            return [dict(r) for r in cursor.fetchall()]

    def get_error_distribution(self) -> Dict[str, int]:
        """Calculates taxonomy distribution of recorded mistakes."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
            SELECT error_type, COUNT(*) as count 
            FROM error_memory 
            GROUP BY error_type
            """)
            dist = {row["error_type"]: row["count"] for row in cursor.fetchall()}

        # Populate defaults
        default_keys = ["FALSE_POSITIVE", "FALSE_NEGATIVE", "WRONG_CLASS", "POOR_BBOX", "INCORRECT_MASK", "UNKNOWN_OBJECT"]
        for k in default_keys:
            dist.setdefault(k, 0)
        return dist

    def get_all_errors(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute("""
            SELECT error_id, review_id, image_id, predicted_class, correct_class, predicted_confidence, 
                   error_type, training_action, crop_path, recurrence_count, created_at 
            FROM error_memory 
            ORDER BY created_at DESC LIMIT ?
            """, (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def get_error_statistics(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            tot = conn.execute("SELECT COUNT(*) as c FROM error_memory").fetchone()["c"]
        return {
            "total_errors": tot,
            "error_distribution": self.get_error_distribution(),
            "top_recurring_errors": self.get_recurring_error_matrix()
        }
