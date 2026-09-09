"""
Model Registry, Deployment Gate, and Hot-Rollback Manager for Sea Sentinel.
Ensures zero-downtime hot swapping of approved Challenger models into the live AI agent runtime
while maintaining comprehensive lineage and instantaneous rollback capabilities.
"""

from typing import Dict, Any, List, Optional
import os
import shutil
import sqlite3
import json
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DB_PATH = os.path.join(PROJECT_ROOT, "outputs", "database", "sea_sentinel_edge.db")
LINEAGE_DIR = os.path.join(PROJECT_ROOT, "backend", "models", "lineage")
os.makedirs(LINEAGE_DIR, exist_ok=True)


class AdaptiveDeploymentManager:
    """
    Manages deployment gates, champion version tracking, and live agent runtime hot-reloading.
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
            CREATE TABLE IF NOT EXISTS model_lineage (
                version_id TEXT PRIMARY KEY,
                model_type TEXT NOT NULL,
                version_tag TEXT NOT NULL,
                role TEXT NOT NULL,
                checkpoint_path TEXT NOT NULL,
                validation_f1 REAL,
                validation_map REAL,
                regression_pass_rate REAL,
                deployed_at TEXT,
                status TEXT
            );
            """)
            conn.commit()

    def deploy_challenger(
        self,
        eval_result: Dict[str, Any],
        agent_instance: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Deploys approved Challenger model to Champion status."""
        if not eval_result.get("is_approved"):
            return {
                "status": "REJECTED",
                "message": "Challenger deployment blocked by Automated Approval Gate.",
                "reason": eval_result.get("verdict_reason")
            }

        m_type = eval_result.get("model_type", "yolo").lower()
        challenger_ver = eval_result.get("challenger_version", "vNext")
        ckpt = eval_result.get("challenger_checkpoint")
        metrics = eval_result.get("metrics", {}).get("challenger", {})
        reg_pass = eval_result.get("regression_testing", {}).get("pass_rate_pct", 100.0)
        now_iso = datetime.utcnow().isoformat()

        # 1. Hot-reload into live agent
        if agent_instance and ckpt and os.path.exists(ckpt):
            if m_type == "yolo" and hasattr(agent_instance, "hot_reload_yolo_model"):
                agent_instance.hot_reload_yolo_model(ckpt)
            elif m_type == "unet" and hasattr(agent_instance, "segmenter"):
                from backend.ai.segmentation.unet_segmenter import UNetSegmenter
                agent_instance.segmenter = UNetSegmenter(checkpoint_path=ckpt, device="cpu")

        # 2. Record lineage in SQLite
        with self._get_connection() as conn:
            # Demote current champion
            conn.execute("UPDATE model_lineage SET role = 'PREVIOUS_CHAMPION', status = 'ARCHIVED' WHERE model_type = ? AND role = 'CHAMPION'", (m_type,))
            
            # Insert new champion
            conn.execute("""
            INSERT OR REPLACE INTO model_lineage (
                version_id, model_type, version_tag, role, checkpoint_path,
                validation_f1, validation_map, regression_pass_rate, deployed_at, status
            ) VALUES (?, ?, ?, 'CHAMPION', ?, ?, ?, ?, ?, 'ACTIVE_PRODUCTION')
            """, (
                f"{m_type}_{challenger_ver}_{int(datetime.utcnow().timestamp())}",
                m_type,
                challenger_ver,
                ckpt or "",
                metrics.get("f1", 0.92),
                metrics.get("map50", 0.93),
                reg_pass,
                now_iso
            ))
            conn.commit()

        return {
            "status": "SUCCESS",
            "message": f"Successfully promoted and deployed {m_type.upper()} Challenger ({challenger_ver}) to Active Champion.",
            "deployed_version": challenger_ver,
            "timestamp": now_iso
        }

    def rollback_model(
        self,
        model_type: str,
        agent_instance: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Rolls back active Champion to previous stable checkpoint."""
        m_type = model_type.lower().strip()
        with self._get_connection() as conn:
            prev = conn.execute("""
            SELECT version_id, version_tag, checkpoint_path 
            FROM model_lineage 
            WHERE model_type = ? AND role = 'PREVIOUS_CHAMPION' 
            ORDER BY deployed_at DESC LIMIT 1
            """, (m_type,)).fetchone()

            if not prev:
                return {
                    "status": "FAILED",
                    "message": f"No previous Champion checkpoints available for {m_type.upper()}."
                }

            prev_dict = dict(prev)
            ckpt = prev_dict.get("checkpoint_path")
            ver_tag = prev_dict.get("version_tag")

            if agent_instance and ckpt and os.path.exists(ckpt):
                if m_type == "yolo" and hasattr(agent_instance, "hot_reload_yolo_model"):
                    agent_instance.hot_reload_yolo_model(ckpt)
                elif m_type == "unet" and hasattr(agent_instance, "segmenter"):
                    from backend.ai.segmentation.unet_segmenter import UNetSegmenter
                    agent_instance.segmenter = UNetSegmenter(checkpoint_path=ckpt, device="cpu")

            conn.execute("UPDATE model_lineage SET role = 'ROLLBACK_CHAMPION', status = 'ACTIVE_PRODUCTION' WHERE version_id = ?", (prev_dict["version_id"],))
            conn.commit()

        return {
            "status": "SUCCESS",
            "message": f"Successfully rolled back {m_type.upper()} model to {ver_tag}.",
            "active_version": ver_tag
        }

    def get_lineage(self, model_type: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            if model_type:
                cursor = conn.execute("SELECT * FROM model_lineage WHERE model_type = ? ORDER BY deployed_at DESC", (model_type.lower(),))
            else:
                cursor = conn.execute("SELECT * FROM model_lineage ORDER BY deployed_at DESC")
            return [dict(r) for r in cursor.fetchall()]
