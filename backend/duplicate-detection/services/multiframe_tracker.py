"""Multi-frame Trajectory Correlator & Duplicate Target Deduplicator."""
import numpy as np
from typing import List, Dict, Any

class MultiFrameTrackerService:
    def __init__(self, max_distance_px: float = 80.0):
        self.max_distance_px = max_distance_px
        self.tracked_targets: List[Dict[str, Any]] = []

    def process_frame(self, frame_idx: int, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduplicated = []
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            
            is_dup = False
            for trk in self.tracked_targets:
                tcx, tcy = trk["centroid"]
                dist = np.sqrt((cx - tcx)**2 + (cy - tcy)**2)
                if dist < self.max_distance_px and trk["class_name"] == det["class_name"]:
                    is_dup = True
                    det["track_id"] = trk["track_id"]
                    trk["last_seen_frame"] = frame_idx
                    break
                    
            if not is_dup:
                track_id = f"TRK-{len(self.tracked_targets)+1:03d}"
                det["track_id"] = track_id
                self.tracked_targets.append({
                    "track_id": track_id,
                    "centroid": (cx, cy),
                    "class_name": det["class_name"],
                    "first_seen_frame": frame_idx,
                    "last_seen_frame": frame_idx
                })
            deduplicated.append(det)
        return deduplicated
