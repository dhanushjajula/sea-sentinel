"""
Repeat Survey Change Detection & Underwater Object Drift Prediction Engine.
Performs cross-survey spatiotemporal matching, identifies persistent/new/moved marine debris,
and calculates drift trajectories without cloud dependencies.
"""

from typing import Dict, Any, List, Optional, Tuple
import os
import math
from datetime import datetime


class SurveyChangeDetector:
    """
    Compares consecutive sonar surveys to track debris movement, migration, and degradation.
    """
    def __init__(self, match_radius_m: float = 35.0):
        self.match_radius_m = match_radius_m

    @staticmethod
    def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371000.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0)**2
        return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    def compare_surveys(
        self,
        current_targets: List[Dict[str, Any]],
        historical_targets: Optional[List[Dict[str, Any]]] = None,
        time_delta_days: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Compares current detections against prior survey detections.
        """
        if not historical_targets or len(historical_targets) == 0:
            return {
                "status": "UNAVAILABLE",
                "reason": "Single survey mode — No prior baseline survey data available in local database.",
                "change_summary": {
                    "new_objects": len(current_targets),
                    "persistent_objects": 0,
                    "moved_objects": 0,
                    "removed_objects": 0
                },
                "matched_targets": [],
                "drift_predictions": []
            }

        matched_current = set()
        matched_hist = set()
        matched_pairs = []
        drift_predictions = []

        for c_idx, curr in enumerate(current_targets):
            c_lat = curr.get("latitude")
            c_lon = curr.get("longitude")
            if c_lat is None or c_lon is None:
                continue

            best_dist = float("inf")
            best_h_idx = None

            for h_idx, hist in enumerate(historical_targets):
                if h_idx in matched_hist:
                    continue
                h_lat = hist.get("latitude")
                h_lon = hist.get("longitude")
                if h_lat is None or h_lon is None:
                    continue

                dist = self._haversine_m(c_lat, c_lon, h_lat, h_lon)
                if dist < best_dist and dist <= self.match_radius_m:
                    best_dist = dist
                    best_h_idx = h_idx

            if best_h_idx is not None:
                matched_current.add(c_idx)
                matched_hist.add(best_h_idx)
                hist_match = historical_targets[best_h_idx]
                
                # Check displacement
                is_moved = best_dist > 5.0
                status_label = "MOVED_OBJECT" if is_moved else "PERSISTENT_OBJECT"

                # Calculate drift vector
                bearing_deg = 0.0
                if is_moved:
                    d_lon = math.radians(c_lon - hist_match["longitude"])
                    y = math.sin(d_lon) * math.cos(math.radians(c_lat))
                    x = math.cos(math.radians(hist_match["latitude"])) * math.sin(math.radians(c_lat)) - \
                        math.sin(math.radians(hist_match["latitude"])) * math.cos(math.radians(c_lat)) * math.cos(d_lon)
                    bearing_deg = (math.degrees(math.atan2(y, x)) + 360) % 360

                drift_rate_m_day = (best_dist / max(0.1, time_delta_days)) if time_delta_days else 0.0

                matched_pairs.append({
                    "object_id": curr.get("object_id"),
                    "class": curr.get("class"),
                    "status": status_label,
                    "displacement_m": round(best_dist, 2),
                    "bearing_deg": round(bearing_deg, 1),
                    "historical_id": hist_match.get("object_id")
                })

                if is_moved and time_delta_days and time_delta_days > 0:
                    # Predict position 7 days forward based on drift vector
                    pred_lat = c_lat + (c_lat - hist_match["latitude"]) * (7.0 / time_delta_days)
                    pred_lon = c_lon + (c_lon - hist_match["longitude"]) * (7.0 / time_delta_days)
                    drift_predictions.append({
                        "object_id": curr.get("object_id"),
                        "class": curr.get("class"),
                        "observed_position": {"latitude": c_lat, "longitude": c_lon},
                        "predicted_position_7d": {"latitude": round(pred_lat, 6), "longitude": round(pred_lon, 6)},
                        "drift_rate_m_per_day": round(drift_rate_m_day, 2),
                        "drift_bearing_deg": round(bearing_deg, 1),
                        "confidence": "ESTIMATED_FROM_SURVEY_DELTA"
                    })

        new_count = len(current_targets) - len(matched_current)
        removed_count = len(historical_targets) - len(matched_hist)
        persistent_count = len([p for p in matched_pairs if p["status"] == "PERSISTENT_OBJECT"])
        moved_count = len([p for p in matched_pairs if p["status"] == "MOVED_OBJECT"])

        return {
            "status": "COMPUTED",
            "change_summary": {
                "new_objects": new_count,
                "persistent_objects": persistent_count,
                "moved_objects": moved_count,
                "removed_objects": removed_count,
                "total_current": len(current_targets),
                "total_historical": len(historical_targets)
            },
            "matched_targets": matched_pairs,
            "drift_predictions": drift_predictions
        }
