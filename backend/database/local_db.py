"""
Local SQLite Database Manager for Sea Sentinel (Edge-First, Offline-Native).
Stores surveys, image metadata, detections, GIS events, sync queues, and model registries.
"""

from typing import Dict, Any, List, Optional
import os
import json
import sqlite3
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_DIR = os.path.join(PROJECT_ROOT, "outputs", "database")
DB_PATH = os.path.join(DB_DIR, "sea_sentinel_edge.db")


class LocalDatabase:
    """
    Robust local SQLite database with automatic table creation, WAL mode for fast concurrency,
    and structured querying for offline edge deployments.
    """
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_schema()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_schema(self):
        with self.get_connection() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS surveys (
                survey_id TEXT PRIMARY KEY,
                image_id TEXT,
                image_name TEXT,
                timestamp TEXT,
                processing_mode TEXT,
                hardware TEXT,
                latency_ms REAL,
                total_objects INTEGER DEFAULT 0,
                status TEXT,
                sync_status TEXT DEFAULT 'PENDING',
                synced_at TEXT,
                metadata_json TEXT
            );

            CREATE TABLE IF NOT EXISTS detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                survey_id TEXT,
                object_id TEXT,
                class_label TEXT,
                confidence REAL,
                detection_source TEXT,
                bbox_json TEXT,
                segmentation_json TEXT,
                latitude REAL,
                longitude REAL,
                length_m REAL,
                width_m REAL,
                area_m2 REAL,
                risk_score TEXT,
                risk_category TEXT,
                habitat_overlap_json TEXT,
                created_at TEXT,
                FOREIGN KEY (survey_id) REFERENCES surveys(survey_id)
            );

            CREATE TABLE IF NOT EXISTS sync_queue (
                queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                survey_id TEXT UNIQUE,
                payload_json TEXT,
                enqueued_at TEXT,
                sync_status TEXT DEFAULT 'PENDING',
                attempts INTEGER DEFAULT 0,
                last_error TEXT,
                synced_at TEXT
            );

            CREATE TABLE IF NOT EXISTS model_registry (
                model_name TEXT,
                version TEXT,
                architecture TEXT,
                checksum_sha256 TEXT,
                weights_path TEXT,
                is_active INTEGER DEFAULT 1,
                status TEXT,
                updated_at TEXT,
                PRIMARY KEY (model_name, version)
            );

            CREATE TABLE IF NOT EXISTS benchmark_history (
                run_id TEXT PRIMARY KEY,
                timestamp TEXT,
                sample_count INTEGER,
                p50_ms REAL,
                p95_ms REAL,
                max_ms REAL,
                avg_ms REAL,
                slowest_component TEXT,
                budget_status TEXT,
                system_specs TEXT
            );
            """)
            conn.commit()

    def insert_survey(self, survey_data: Dict[str, Any], detections: List[Dict[str, Any]]) -> str:
        """Inserts completed survey and associated detections, queuing for cloud sync."""
        s_id = survey_data.get("survey_id") or survey_data.get("analysis_id") or f"SURV_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        ts = survey_data.get("timestamp") or datetime.utcnow().isoformat()
        mode = survey_data.get("processing_mode") or survey_data.get("mode") or "balanced"
        hw = survey_data.get("hardware") or "CPU_EDGE"
        latency = survey_data.get("latency_ms") or 0.0

        with self.get_connection() as conn:
            conn.execute("""
            INSERT OR REPLACE INTO surveys 
            (survey_id, image_id, image_name, timestamp, processing_mode, hardware, latency_ms, total_objects, status, sync_status, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)
            """, (
                s_id,
                survey_data.get("image_id", s_id),
                survey_data.get("image_name", "sonar_scan.png"),
                ts,
                mode,
                hw,
                latency,
                len(detections),
                "COMPLETED",
                json.dumps(survey_data)
            ))

            for d in detections:
                conn.execute("""
                INSERT INTO detections 
                (survey_id, object_id, class_label, confidence, detection_source, bbox_json, segmentation_json, 
                 latitude, longitude, length_m, width_m, area_m2, risk_score, risk_category, habitat_overlap_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    s_id,
                    d.get("object_id", "OBJ_001"),
                    d.get("class", "debris"),
                    float(d.get("calibrated_confidence", d.get("confidence", 0.8))),
                    "/".join(d.get("sources", ["fusion"])),
                    json.dumps(d.get("bbox", [])),
                    json.dumps(d.get("polygon", [])),
                    d.get("latitude"),
                    d.get("longitude"),
                    d.get("length_m", 1.0),
                    d.get("width_m", 1.0),
                    d.get("area_sq_m", 1.0),
                    d.get("risk_score", "MEDIUM"),
                    d.get("risk_category", "MODERATE"),
                    json.dumps(d.get("habitat_overlaps", [])),
                    ts
                ))

            # Store in sync queue
            full_payload = {
                "survey": survey_data,
                "detections": detections,
                "created_at": ts
            }
            conn.execute("""
            INSERT OR REPLACE INTO sync_queue (survey_id, payload_json, enqueued_at, sync_status, attempts)
            VALUES (?, ?, ?, 'PENDING', 0)
            """, (s_id, json.dumps(full_payload), ts))
            conn.commit()

        return s_id

    def get_recent_surveys(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.execute("""
            SELECT survey_id, image_name, timestamp, processing_mode, latency_ms, total_objects, status, sync_status 
            FROM surveys ORDER BY timestamp DESC LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_all_georeferenced_targets(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.execute("""
            SELECT d.*, s.image_name, s.timestamp as survey_time
            FROM detections d
            JOIN surveys s ON d.survey_id = s.survey_id
            WHERE d.latitude IS NOT NULL AND d.longitude IS NOT NULL
            ORDER BY d.created_at DESC
            """)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
