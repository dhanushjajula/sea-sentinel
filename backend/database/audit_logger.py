"""Audit Logger for SQLite persistence."""
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from backend.database.connection import get_db_connection
from backend.shared.utils.logger import get_logger

logger = get_logger("audit_logger", "backend")

class AuditLogger:
    def __init__(self):
        self._init_db()

    def _init_db(self):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                survey_id TEXT NOT NULL,
                image_name TEXT NOT NULL,
                target_count INTEGER,
                targets_json TEXT,
                latency_ms REAL,
                status TEXT
            )
        """)
        conn.commit()
        conn.close()

    def log_survey_run(self, survey_id: str, image_name: str, target_count: int, targets_json: str, latency_ms: float, status: str = "SUCCESS"):
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO audit_logs (timestamp, survey_id, image_name, target_count, targets_json, latency_ms, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (datetime.utcnow().isoformat(), survey_id, image_name, target_count, targets_json, latency_ms, status))
            conn.commit()
            conn.close()
            logger.info(f"Logged survey {survey_id} ({target_count} targets) to SQLite audit log.")
        except Exception as e:
            logger.error(f"Failed to log survey to database: {e}")

    def get_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,))
        rows = [dict(row) for row in cur.fetchall()]
        conn.close()
        return rows
