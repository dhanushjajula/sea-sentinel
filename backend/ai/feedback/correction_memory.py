"""
Correction Memory Engine
Maintains persistent SQLite memory of human-corrected detections, extracts invariant
acoustic visual signatures, and performs cosine similarity matching on future detections
to prevent YOLO from repeating identical misclassifications.
"""

from typing import Dict, Any, List, Optional, Tuple, Union
import os
import sqlite3
import json
import uuid
import math
from datetime import datetime
import numpy as np
import cv2


class CorrectionMemory:
    """
    Long-term episodic memory for human corrections on side-scan sonar detections.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_dir = os.path.join(base_dir, "outputs", "audit")
            os.makedirs(db_dir, exist_ok=True)
            self.db_path = os.path.join(db_dir, "survey_audit.db")
        else:
            self.db_path = db_path
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

        self.crops_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "outputs", "feedback", "crops"
        )
        os.makedirs(self.crops_dir, exist_ok=True)

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes relational table for correction memory."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS correction_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    feedback_id TEXT UNIQUE NOT NULL,
                    session_id TEXT,
                    object_id TEXT,
                    source_image_path TEXT,
                    crop_path TEXT NOT NULL,
                    bbox_json TEXT NOT NULL,
                    original_class TEXT NOT NULL,
                    original_confidence REAL,
                    corrected_class TEXT NOT NULL,
                    corrected_class_id INTEGER NOT NULL,
                    correction_type TEXT NOT NULL,
                    human_comment TEXT NOT NULL,
                    extracted_reason TEXT,
                    feature_vector_json TEXT NOT NULL,
                    aspect_ratio REAL,
                    applied_count INTEGER DEFAULT 0,
                    is_trained INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_corr_orig_cls ON correction_memory(original_class);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_corr_trained ON correction_memory(is_trained);")
            conn.commit()
        finally:
            conn.close()

    # -----------------------------------------------------------------
    # Visual Acoustic Feature Extraction
    # -----------------------------------------------------------------
    @staticmethod
    def extract_crop_features(crop: np.ndarray) -> np.ndarray:
        """
        Computes a standardized 32-dimensional acoustic invariant feature vector:
          - Normalized 16-bin backscatter intensity distribution
          - 7 log-transformed Hu geometric moments
          - 6 directional gradient energy ratios (Sobel X and Y)
          - Aspect ratio, relative intensity standard deviation, and density
        Vector is L2-normalized for cosine similarity computation.
        """
        if crop is None or crop.size == 0:
            return np.zeros(32, dtype=np.float32)

        # Convert to single-channel uint8
        if len(crop.shape) == 3:
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        else:
            gray = crop.copy()

        if gray.dtype != np.uint8:
            gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

        # Standardize patch scale
        h_orig, w_orig = gray.shape[:2]
        aspect_ratio = float(max(w_orig, h_orig)) / max(1.0, float(min(w_orig, h_orig)))
        norm_patch = cv2.resize(gray, (64, 64), interpolation=cv2.INTER_AREA)

        # 1. Intensity Histogram (16 bins)
        hist = cv2.calcHist([norm_patch], [0], None, [16], [0, 256]).flatten()
        hist = hist / max(1.0, float(np.sum(hist)))

        # 2. Hu Spatial Moments (7 moments)
        moments = cv2.moments(norm_patch)
        hu = cv2.HuMoments(moments).flatten()
        # Log scale transform for numerical stability
        hu_log = []
        for val in hu:
            val = float(val)
            if abs(val) > 1e-12:
                hu_log.append(-1.0 * math.copysign(1.0, val) * math.log10(abs(val)))
            else:
                hu_log.append(0.0)
        hu_features = np.array(hu_log, dtype=np.float32)

        # 3. Directional Gradient Energy (6 bins)
        sobel_x = cv2.Sobel(norm_patch, cv2.CV_32F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(norm_patch, cv2.CV_32F, 0, 1, ksize=3)
        mag, angle = cv2.cartToPolar(sobel_x, sobel_y, angleInDegrees=True)
        grad_hist, _ = np.histogram(angle, bins=6, range=(0, 360), weights=mag)
        grad_hist = grad_hist / max(1.0, float(np.sum(grad_hist)))

        # 4. Geometry and Texture Moments (3 scalars)
        mean_val = float(np.mean(norm_patch)) / 255.0
        std_val = float(np.std(norm_patch)) / 255.0
        norm_aspect = min(10.0, aspect_ratio) / 10.0

        vector = np.concatenate([
            hist.astype(np.float32),          # 16
            hu_features.astype(np.float32),    # 7
            grad_hist.astype(np.float32),      # 6
            np.array([mean_val, std_val, norm_aspect], dtype=np.float32) # 3
        ])  # Total = 32 dimensions

        # L2-normalize vector
        norm = np.linalg.norm(vector)
        if norm > 1e-6:
            vector = vector / norm
        return vector

    # -----------------------------------------------------------------
    # Save & Learn Human Correction
    # -----------------------------------------------------------------
    def save_correction(
        self,
        source_image: Union[str, np.ndarray],
        bbox: Dict[str, Any],
        original_class: str,
        corrected_class: str,
        corrected_class_id: int,
        human_comment: str,
        extracted_reason: str,
        correction_type: str = "reclassify",
        original_confidence: float = 0.5,
        session_id: Optional[str] = None,
        object_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extracts crop, computes visual signature, and stores in SQLite Correction Memory.
        """
        feedback_id = f"FB_{uuid.uuid4().hex[:8].upper()}"

        # 1. Load source image if string path
        if isinstance(source_image, str):
            image_path = source_image
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"Source sonar image not found: {image_path}")
            img_mat = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        else:
            image_path = "memory_buffer"
            img_mat = source_image

        if img_mat is None:
            raise ValueError("Unable to read sonar image canvas for feedback crop.")

        h_img, w_img = img_mat.shape[:2]
        x1 = max(0, min(w_img - 1, int(round(float(bbox.get("x1", 0))))))
        y1 = max(0, min(h_img - 1, int(round(float(bbox.get("y1", 0))))))
        x2 = max(x1 + 4, min(w_img, int(round(float(bbox.get("x2", w_img))))))
        y2 = max(y1 + 4, min(h_img, int(round(float(bbox.get("y2", h_img))))))

        crop_mat = img_mat[y1:y2, x1:x2]
        if crop_mat.size == 0:
            crop_mat = np.zeros((64, 64), dtype=np.uint8)

        # 2. Save crop to disk
        safe_obj = object_id or "TGT"
        crop_filename = f"{feedback_id}_{safe_obj}.png"
        crop_filepath = os.path.join(self.crops_dir, crop_filename)

        save_mat = crop_mat
        if save_mat.dtype != np.uint8:
            save_mat = cv2.normalize(save_mat, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        cv2.imwrite(crop_filepath, save_mat)

        # 3. Compute invariant feature vector
        feat_vec = self.extract_crop_features(crop_mat)
        feat_json = json.dumps(feat_vec.tolist())

        bw = max(1, x2 - x1)
        bh = max(1, y2 - y1)
        aspect = round(float(max(bw, bh)) / max(1.0, float(min(bw, bh))), 2)
        created_at = datetime.utcnow().isoformat() + "Z"

        # 4. Insert into SQLite
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO correction_memory (
                    feedback_id, session_id, object_id, source_image_path, crop_path,
                    bbox_json, original_class, original_confidence, corrected_class,
                    corrected_class_id, correction_type, human_comment, extracted_reason,
                    feature_vector_json, aspect_ratio, applied_count, is_trained, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)
            """, (
                feedback_id, session_id or "", object_id or "", image_path,
                crop_filepath, json.dumps(bbox), original_class, float(original_confidence),
                corrected_class, int(corrected_class_id), correction_type,
                human_comment, extracted_reason, feat_json, aspect, created_at
            ))
            conn.commit()
        finally:
            conn.close()

        return {
            "feedback_id": feedback_id,
            "session_id": session_id,
            "object_id": object_id,
            "crop_path": crop_filepath,
            "crop_url": f"/static/feedback/crops/{crop_filename}",
            "original_class": original_class,
            "corrected_class": corrected_class,
            "corrected_class_id": corrected_class_id,
            "correction_type": correction_type,
            "extracted_reason": extracted_reason,
            "created_at": created_at
        }

    # -----------------------------------------------------------------
    # Future Detection Matching ("Similar previous mistake?")
    # -----------------------------------------------------------------
    def find_similar_mistake(
        self,
        candidate_crop: np.ndarray,
        candidate_class: str,
        similarity_threshold: float = 0.78
    ) -> Dict[str, Any]:
        """
        Compares candidate detection against Correction Memory.
        If a similar past detection was previously corrected, returns the correction details.
        """
        if candidate_crop is None or candidate_crop.size == 0:
            return {"matched": False}

        cand_vec = self.extract_crop_features(candidate_crop)

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Find past mistakes that originally had the SAME class or similar morphology
            cursor.execute("""
                SELECT id, feedback_id, original_class, corrected_class, corrected_class_id,
                       correction_type, human_comment, extracted_reason, crop_path,
                       feature_vector_json, applied_count
                FROM correction_memory
                WHERE original_class = ? OR corrected_class != ?
            """, (candidate_class, candidate_class))
            rows = cursor.fetchall()

            if not rows:
                return {"matched": False}

            best_sim = -1.0
            best_row = None

            for row in rows:
                try:
                    mem_vec = np.array(json.loads(row["feature_vector_json"]), dtype=np.float32)
                    # Cosine similarity (vectors are unit normalized)
                    sim = float(np.dot(cand_vec, mem_vec))
                    
                    # If this correction originally had the same candidate class, slightly boost confidence
                    if row["original_class"] == candidate_class:
                        sim += 0.04

                    if sim > best_sim:
                        best_sim = sim
                        best_row = row
                except Exception:
                    continue

            if best_row is not None and best_sim >= similarity_threshold:
                # Increment applied count
                cursor.execute("""
                    UPDATE correction_memory
                    SET applied_count = applied_count + 1
                    WHERE id = ?
                """, (best_row["id"],))
                conn.commit()

                return {
                    "matched": True,
                    "feedback_id": best_row["feedback_id"],
                    "original_class": best_row["original_class"],
                    "corrected_class": best_row["corrected_class"],
                    "corrected_class_id": best_row["corrected_class_id"],
                    "correction_type": best_row["correction_type"],
                    "similarity": round(float(min(0.99, best_sim)), 3),
                    "human_comment": best_row["human_comment"],
                    "extracted_reason": best_row["extracted_reason"],
                    "crop_path": best_row["crop_path"],
                    "applied_count": best_row["applied_count"] + 1
                }

            return {"matched": False, "best_similarity": round(float(best_sim), 3) if best_row else 0.0}
        finally:
            conn.close()

    # -----------------------------------------------------------------
    # Stats & Catalog Queries
    # -----------------------------------------------------------------
    def get_all_corrections(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieves stored correction memory records."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT feedback_id, session_id, object_id, source_image_path, crop_path,
                       original_class, original_confidence, corrected_class,
                       corrected_class_id, correction_type, human_comment,
                       extracted_reason, applied_count, is_trained, created_at
                FROM correction_memory
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_recent_corrections(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self.get_all_corrections(limit=limit)

    def get_stats(self) -> Dict[str, Any]:
        """Returns aggregate correction statistics."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM correction_memory")
            total = cursor.fetchone()[0]

            cursor.execute("SELECT SUM(applied_count) FROM correction_memory")
            total_applied = cursor.fetchone()[0] or 0

            cursor.execute("SELECT COUNT(*) FROM correction_memory WHERE is_trained = 0")
            pending_training = cursor.fetchone()[0]

            cursor.execute("""
                SELECT corrected_class, COUNT(*) as cnt
                FROM correction_memory
                GROUP BY corrected_class
            """)
            class_counts = {r[0]: r[1] for r in cursor.fetchall()}

            return {
                "total_corrections_learned": total,
                "total_times_applied": total_applied,
                "pending_training_count": pending_training,
                "class_distribution": class_counts
            }
        finally:
            conn.close()

    def mark_trained(self, feedback_ids: Optional[List[str]] = None):
        """Marks corrections as incorporated into fine-tuned weights."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if feedback_ids:
                placeholders = ",".join("?" for _ in feedback_ids)
                cursor.execute(f"UPDATE correction_memory SET is_trained = 1 WHERE feedback_id IN ({placeholders})", feedback_ids)
            else:
                cursor.execute("UPDATE correction_memory SET is_trained = 1 WHERE is_trained = 0")
            conn.commit()
        finally:
            conn.close()
