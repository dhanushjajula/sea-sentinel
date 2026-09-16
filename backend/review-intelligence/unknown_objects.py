"""
Unknown Object Discovery & Candidate Class Lifecycle Subsystem for Sea Sentinel.
Accumulates multi-sample verified examples for novel acoustic debris structures,
enforces quality checks, and manages promotion to formal training ontology.
"""

from typing import Dict, Any, List, Optional
import os
import sqlite3
import json
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DB_PATH = os.path.join(PROJECT_ROOT, "outputs", "database", "sea_sentinel_edge.db")


class UnknownObjectManager:
    """
    Manages discovery, verification thresholds, and training ontology promotion for novel marine target classes.
    """

    MIN_PROMOTION_SAMPLES = 3

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
            CREATE TABLE IF NOT EXISTS candidate_classes (
                candidate_id TEXT PRIMARY KEY,
                class_name TEXT UNIQUE NOT NULL,
                display_name TEXT,
                sample_count INTEGER DEFAULT 1,
                status TEXT DEFAULT 'ACCUMULATING',
                first_seen_at TEXT,
                last_seen_at TEXT,
                promoted_at TEXT
            );

            CREATE TABLE IF NOT EXISTS candidate_samples (
                sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_name TEXT,
                review_id TEXT,
                image_id TEXT,
                crop_path TEXT,
                created_at TEXT,
                FOREIGN KEY (class_name) REFERENCES candidate_classes(class_name)
            );
            """)
            conn.commit()

    def register_unknown_sample(
        self,
        class_name: str,
        review_id: str,
        image_id: str,
        crop_path: str = ""
    ) -> Dict[str, Any]:
        """Registers a verified sample for an unknown or candidate class."""
        cls_clean = class_name.strip().lower().replace(" ", "_")
        now_iso = datetime.utcnow().isoformat()
        cand_id = f"CAND_{cls_clean}"

        with self._get_connection() as conn:
            cur_cls = conn.execute("SELECT sample_count, status FROM candidate_classes WHERE class_name = ?", (cls_clean,)).fetchone()
            if cur_cls:
                cnt = cur_cls["sample_count"] + 1
                status = "READY_FOR_PROMOTION" if cnt >= self.MIN_PROMOTION_SAMPLES else "ACCUMULATING"
                conn.execute("""
                UPDATE candidate_classes 
                SET sample_count = ?, last_seen_at = ?, status = ? 
                WHERE class_name = ?
                """, (cnt, now_iso, status, cls_clean))
            else:
                cnt = 1
                status = "ACCUMULATING"
                display_name = class_name.replace("_", " ").title()
                conn.execute("""
                INSERT INTO candidate_classes (candidate_id, class_name, display_name, sample_count, status, first_seen_at, last_seen_at)
                VALUES (?, ?, ?, 1, 'ACCUMULATING', ?, ?)
                """, (cand_id, cls_clean, display_name, now_iso, now_iso))

            conn.execute("""
            INSERT INTO candidate_samples (class_name, review_id, image_id, crop_path, created_at)
            VALUES (?, ?, ?, ?, ?)
            """, (cls_clean, review_id, image_id, crop_path, now_iso))
            conn.commit()

        return {
            "class_name": cls_clean,
            "sample_count": cnt,
            "status": status,
            "ready_for_promotion": cnt >= self.MIN_PROMOTION_SAMPLES
        }

    def get_candidate_classes(self) -> List[Dict[str, Any]]:
        """Returns all candidate novel classes and their accumulated verification counts."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
            SELECT candidate_id, class_name, display_name, sample_count, status, first_seen_at, last_seen_at, promoted_at 
            FROM candidate_classes 
            ORDER BY sample_count DESC
            """)
            return [dict(r) for r in cursor.fetchall()]

    def promote_candidate_class(self, class_name: str) -> Dict[str, Any]:
        """Formally promotes candidate class into the active training ontology."""
        cls_clean = class_name.strip().lower().replace(" ", "_")
        now_iso = datetime.utcnow().isoformat()

        with self._get_connection() as conn:
            conn.execute("""
            UPDATE candidate_classes 
            SET status = 'PROMOTED', promoted_at = ? 
            WHERE class_name = ?
            """, (now_iso, cls_clean))
            conn.commit()

        return {
            "status": "SUCCESS",
            "message": f"Candidate class '{cls_clean}' promoted to formal training ontology.",
            "class_name": cls_clean,
            "promoted_at": now_iso
        }
