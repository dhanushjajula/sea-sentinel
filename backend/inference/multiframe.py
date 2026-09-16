"""
Multi-Frame Temporal & Spatial Association Tracker
Associates candidate detections across consecutive Side-Scan Sonar survey frames / pings.
Maintains persistent track IDs, tolerates intermittent single-model dropouts,
and builds cumulative target confidence.
"""

from typing import Dict, Any, List, Optional
import math
import time


class MultiFrameTracker:
    """
    Temporal tracker across sequential sonar frames.
    Links candidate detections into persistent tracks.
    """
    def __init__(
        self,
        max_frame_gap: int = 5,
        spatial_distance_threshold_px: float = 80.0,
        trajectory_weight: float = 0.60,
        iou_weight: float = 0.40
    ):
        self.max_frame_gap = max_frame_gap
        self.spatial_distance_threshold_px = spatial_distance_threshold_px
        self.trajectory_weight = trajectory_weight
        self.iou_weight = iou_weight

        # Active tracks dictionary: {track_id: track_data}
        self.active_tracks: Dict[str, Dict[str, Any]] = {}
        self.next_track_num = 1
        self.current_frame_idx = 0

    def update_frame(
        self,
        frame_idx: int,
        candidates: List[Dict[str, Any]],
        nav_coords: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Updates active tracks with candidate detections from the new frame.
        Returns the updated list of candidates with persistent 'track_id' and 'frame_history'.
        """
        self.current_frame_idx = frame_idx
        updated_candidates = []

        unmatched_candidates = list(range(len(candidates)))
        unmatched_tracks = set(self.active_tracks.keys())

        # Match candidates to active tracks
        matches = []
        for c_idx in unmatched_candidates:
            cand = candidates[c_idx]
            c_cent = cand.get("centroid", cand.get("center", [0, 0]))
            c_box = cand.get("bbox", {})

            for track_id, track in self.active_tracks.items():
                last_cent = track["last_centroid"]
                dist = math.hypot(c_cent[0] - last_cent[0], c_cent[1] - last_cent[1])

                if dist <= self.spatial_distance_threshold_px:
                    iou = self._calc_box_iou(c_box, track["last_bbox"])
                    sim_score = (self.trajectory_weight * (1.0 - dist / self.spatial_distance_threshold_px)) + (self.iou_weight * iou)
                    matches.append({
                        "cand_idx": c_idx,
                        "track_id": track_id,
                        "score": sim_score,
                        "dist": dist
                    })

        # Sort matches by similarity score descending
        matches.sort(key=lambda m: m["score"], reverse=True)
        assigned_cands = set()
        assigned_tracks = set()

        for m in matches:
            c_idx = m["cand_idx"]
            t_id = m["track_id"]
            if c_idx in assigned_cands or t_id in assigned_tracks:
                continue

            assigned_cands.add(c_idx)
            assigned_tracks.add(t_id)

            cand = candidates[c_idx]
            rec = dict(cand)

            track = self.active_tracks[t_id]
            track["last_frame"] = frame_idx
            track["last_centroid"] = cand.get("centroid", [0, 0])
            track["last_bbox"] = cand.get("bbox", {})
            track["detection_count"] += 1
            track["sources_observed"].extend(cand.get("sources", []))
            track["history"].append({
                "frame": frame_idx,
                "confidence": cand.get("confidence", 0.5),
                "sources": cand.get("sources", []),
                "category": cand.get("source_category", "SINGLE")
            })

            # Cumulative confidence boost from multi-frame persistence
            base_conf = float(cand.get("confidence", 0.5))
            persistence_boost = min(0.15, track["detection_count"] * 0.04)
            multiframe_conf = min(0.99, round(base_conf + persistence_boost, 3))

            rec["track_id"] = t_id
            rec["multi_frame_hits"] = track["detection_count"]
            rec["multi_frame_confidence"] = multiframe_conf
            rec["confidence"] = multiframe_conf
            updated_candidates.append(rec)

        # Create new tracks for unassigned candidates
        for c_idx in range(len(candidates)):
            if c_idx not in assigned_cands:
                cand = candidates[c_idx]
                rec = dict(cand)
                track_id = f"TRK_{self.next_track_num:04d}"
                self.next_track_num += 1

                self.active_tracks[track_id] = {
                    "track_id": track_id,
                    "first_frame": frame_idx,
                    "last_frame": frame_idx,
                    "last_centroid": cand.get("centroid", [0, 0]),
                    "last_bbox": cand.get("bbox", {}),
                    "class": cand.get("class", "marine_debris"),
                    "detection_count": 1,
                    "sources_observed": list(cand.get("sources", [])),
                    "history": [{
                        "frame": frame_idx,
                        "confidence": cand.get("confidence", 0.5),
                        "sources": cand.get("sources", []),
                        "category": cand.get("source_category", "SINGLE")
                    }]
                }

                rec["track_id"] = track_id
                rec["multi_frame_hits"] = 1
                rec["multi_frame_confidence"] = cand.get("confidence", 0.5)
                updated_candidates.append(rec)

        # Prune stale tracks exceeding max_frame_gap
        stale_tracks = [
            t_id for t_id, t in self.active_tracks.items()
            if (frame_idx - t["last_frame"]) > self.max_frame_gap
        ]
        for t_id in stale_tracks:
            del self.active_tracks[t_id]

        return updated_candidates

    def process_sequence(
        self,
        sequence_frames: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Processes a sequence of frames and returns multi-frame associated results.
        """
        all_results = []
        for idx, frame_data in enumerate(sequence_frames):
            frame_num = frame_data.get("frame_idx", idx + 1)
            cands = frame_data.get("candidates", [])
            tracked_cands = self.update_frame(frame_num, cands)
            all_results.append({
                "frame_idx": frame_num,
                "objects": tracked_cands
            })

        return {
            "status": "success",
            "total_frames_processed": len(sequence_frames),
            "total_active_tracks": len(self.active_tracks),
            "frames": all_results
        }

    @staticmethod
    def _calc_box_iou(b1: Dict[str, float], b2: Dict[str, float]) -> float:
        x1 = max(float(b1.get("x1", 0)), float(b2.get("x1", 0)))
        y1 = max(float(b1.get("y1", 0)), float(b2.get("y1", 0)))
        x2 = min(float(b1.get("x2", 0)), float(b2.get("x2", 0)))
        y2 = min(float(b1.get("y2", 0)), float(b2.get("y2", 0)))
        inter_w = max(0.0, x2 - x1)
        inter_h = max(0.0, y2 - y1)
        inter_area = inter_w * inter_h
        area1 = max(1.0, (float(b1.get("x2", 0)) - float(b1.get("x1", 0))) * (float(b1.get("y2", 0)) - float(b1.get("y1", 0))))
        area2 = max(1.0, (float(b2.get("x2", 0)) - float(b2.get("x1", 0))) * (float(b2.get("y2", 0)) - float(b2.get("y2", 0))))
        union = area1 + area2 - inter_area
        return float(inter_area / max(1.0, union))
