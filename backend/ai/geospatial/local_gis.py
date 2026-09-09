"""
Local GIS & Marine Ecosystem Risk Engine for Sea Sentinel (Offline-Native)
Handles spatial indexing, habitat intersection, subsea infrastructure overlap,
and multi-tier ecological hazard scoring completely offline using local GeoJSON.
"""

from typing import Dict, Any, List, Tuple, Optional
import os
import json
import math

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
GIS_DATA_DIR = os.path.join(PROJECT_ROOT, "backend", "datasets", "gis_layers")
os.makedirs(GIS_DATA_DIR, exist_ok=True)

# Default high-fidelity local marine GIS layers (WGS84) for offline operations
DEFAULT_GIS_LAYERS = {
    "coral_reefs": {
        "type": "FeatureCollection",
        "name": "Coral Reef Sanctuaries & Ecosystems",
        "category": "sensitive_habitat",
        "risk_multiplier": 2.5,
        "features": [
            {
                "type": "Feature",
                "properties": {"id": "CR_001", "name": "Palk Bay Coral Fringe", "type": "Coral Reef", "sensitivity": "CRITICAL"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[79.15, 9.20], [79.35, 9.20], [79.35, 9.35], [79.15, 9.35], [79.15, 9.20]]]
                }
            },
            {
                "type": "Feature",
                "properties": {"id": "CR_002", "name": "Gulf of Mannar Coral Zone", "type": "Coral Reef", "sensitivity": "CRITICAL"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[78.80, 8.80], [79.10, 8.80], [79.10, 9.10], [78.80, 9.10], [78.80, 8.80]]]
                }
            },
            {
                "type": "Feature",
                "properties": {"id": "CR_003", "name": "Andaman Deep Reef Shelf", "type": "Coral Reef", "sensitivity": "CRITICAL"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[92.60, 11.50], [92.90, 11.50], [92.90, 11.80], [92.60, 11.80], [92.60, 11.50]]]
                }
            }
        ]
    },
    "marine_protected_areas": {
        "type": "FeatureCollection",
        "name": "Marine Protected Areas (MPAs)",
        "category": "regulatory_zone",
        "risk_multiplier": 2.0,
        "features": [
            {
                "type": "Feature",
                "properties": {"id": "MPA_001", "name": "Gulf of Mannar Marine National Park", "type": "MPA", "sensitivity": "HIGH"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[78.60, 8.60], [79.30, 8.60], [79.30, 9.25], [78.60, 9.25], [78.60, 8.60]]]
                }
            },
            {
                "type": "Feature",
                "properties": {"id": "MPA_002", "name": "Malvan Marine Sanctuary", "type": "MPA", "sensitivity": "HIGH"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.40, 15.90], [73.60, 15.90], [73.60, 16.15], [73.40, 16.15], [73.40, 15.90]]]
                }
            }
        ]
    },
    "seagrass_meadows": {
        "type": "FeatureCollection",
        "name": "Seagrass Carbon Meadows",
        "category": "sensitive_habitat",
        "risk_multiplier": 1.8,
        "features": [
            {
                "type": "Feature",
                "properties": {"id": "SG_001", "name": "Palk Strait Inshore Seagrass Beds", "type": "Seagrass", "sensitivity": "MODERATE"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[79.05, 9.25], [79.25, 9.25], [79.25, 9.45], [79.05, 9.45], [79.05, 9.25]]]
                }
            }
        ]
    },
    "underwater_infrastructure": {
        "type": "FeatureCollection",
        "name": "Subsea Cables & Hydrocarbon Pipelines",
        "category": "critical_infrastructure",
        "risk_multiplier": 2.8,
        "features": [
            {
                "type": "Feature",
                "properties": {"id": "INF_001", "name": "Trans-Indian Submarine Fiber Optic Cable 4", "type": "Fiber Cable", "sensitivity": "CRITICAL"},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[78.50, 8.50], [79.00, 9.00], [79.50, 9.40], [80.20, 10.00]]
                }
            },
            {
                "type": "Feature",
                "properties": {"id": "INF_002", "name": "Offshore Gas Gathering Pipeline A", "type": "Gas Pipeline", "sensitivity": "CRITICAL"},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[78.75, 8.95], [79.15, 9.15]]
                }
            }
        ]
    },
    "shipping_lanes": {
        "type": "FeatureCollection",
        "name": "Commercial Shipping Channels & Fairways",
        "category": "navigation_hazard",
        "risk_multiplier": 1.9,
        "features": [
            {
                "type": "Feature",
                "properties": {"id": "NAV_001", "name": "East-West Deepwater Traffic Separation Scheme", "type": "Shipping Channel", "sensitivity": "HIGH"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[78.00, 8.20], [80.50, 8.20], [80.50, 8.45], [78.00, 8.45], [78.00, 8.20]]]
                }
            }
        ]
    }
}


class LocalGISEngine:
    """
    100% Offline GIS Engine calculating spatial intersections, habitat overlaps,
    infrastructure proximity, and ecological risk without remote network calls.
    """
    def __init__(self, data_dir: str = GIS_DATA_DIR):
        self.data_dir = data_dir
        self.layers: Dict[str, Dict[str, Any]] = {}
        self._initialize_layers()

    def _initialize_layers(self):
        """Loads GIS layers from local JSON files or writes defaults if missing."""
        for layer_key, layer_data in DEFAULT_GIS_LAYERS.items():
            file_path = os.path.join(self.data_dir, f"{layer_key}.geojson")
            if not os.path.exists(file_path):
                try:
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(layer_data, f, indent=2)
                except Exception:
                    pass
                self.layers[layer_key] = layer_data
            else:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        self.layers[layer_key] = json.load(f)
                except Exception:
                    self.layers[layer_key] = layer_data

    @staticmethod
    def _haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Computes geodesic distance in meters between two WGS84 coordinates."""
        R = 6371000.0  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        a = (math.sin(delta_phi / 2.0) ** 2 +
             math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return R * c

    @staticmethod
    def _point_in_polygon(lat: float, lon: float, poly_coords: List[List[float]]) -> bool:
        """Ray-casting algorithm to test if (lon, lat) is inside a polygon."""
        inside = False
        n = len(poly_coords)
        for i in range(n):
            p1_lon, p1_lat = poly_coords[i]
            p2_lon, p2_lat = poly_coords[(i + 1) % n]
            if (p1_lat > lat) != (p2_lat > lat):
                x_inters = (lat - p1_lat) * (p2_lon - p1_lon) / (p2_lat - p1_lat + 1e-12) + p1_lon
                if lon < x_inters:
                    inside = not inside
        return inside

    @staticmethod
    def _point_to_line_distance_m(lat: float, lon: float, line_coords: List[List[float]]) -> float:
        """Approximates min geodesic distance from point to a polyline."""
        min_dist = float("inf")
        for p_lon, p_lat in line_coords:
            d = LocalGISEngine._haversine_distance_m(lat, lon, p_lat, p_lon)
            if d < min_dist:
                min_dist = d
        return min_dist

    def evaluate_target_risk(
        self,
        lat: Optional[float],
        lon: Optional[float],
        target_class: str,
        confidence: float,
        length_m: float = 1.0,
        width_m: float = 1.0
    ) -> Dict[str, Any]:
        """
        Evaluates ecological and navigational hazard for a single sonar target against local GIS layers.
        """
        if lat is None or lon is None:
            return {
                "status": "UNREFERENCED",
                "risk_score": "MEDIUM",
                "risk_category": "MODERATE",
                "hazard_summary": "Unreferenced acoustic target; baseline priority assigned.",
                "habitat_overlaps": [],
                "nearest_infrastructure_m": None,
                "overall_risk_index": 0.45
            }

        overlaps = []
        nearest_infra_dist = float("inf")
        max_multiplier = 1.0

        for layer_key, layer_info in self.layers.items():
            multiplier = layer_info.get("risk_multiplier", 1.0)
            features = layer_info.get("features", [])

            for feat in features:
                props = feat.get("properties", {})
                geom = feat.get("geometry", {})
                g_type = geom.get("type")
                coords = geom.get("coordinates", [])

                if g_type == "Polygon" and coords:
                    is_inside = self._point_in_polygon(lat, lon, coords[0])
                    if is_inside:
                        overlaps.append({
                            "layer": layer_key,
                            "name": props.get("name"),
                            "type": props.get("type"),
                            "sensitivity": props.get("sensitivity", "HIGH"),
                            "intersection": True,
                            "distance_m": 0.0
                        })
                        if multiplier > max_multiplier:
                            max_multiplier = multiplier
                    else:
                        # Check proximity (buffer within 500m)
                        poly_pts = coords[0]
                        min_d = min([self._haversine_distance_m(lat, lon, p_lat, p_lon) for p_lon, p_lat in poly_pts]) if poly_pts else float("inf")
                        if min_d < 500.0:
                            overlaps.append({
                                "layer": layer_key,
                                "name": props.get("name"),
                                "type": props.get("type"),
                                "sensitivity": props.get("sensitivity", "MODERATE"),
                                "intersection": False,
                                "distance_m": round(min_d, 1)
                            })

                elif g_type == "LineString" and coords:
                    line_dist = self._point_to_line_distance_m(lat, lon, coords)
                    if line_dist < nearest_infra_dist:
                        nearest_infra_dist = line_dist
                    if line_dist < 150.0:  # Critical proximity to subsea infrastructure
                        overlaps.append({
                            "layer": layer_key,
                            "name": props.get("name"),
                            "type": props.get("type"),
                            "sensitivity": "CRITICAL",
                            "intersection": line_dist < 20.0,
                            "distance_m": round(line_dist, 1)
                        })
                        if multiplier > max_multiplier:
                            max_multiplier = multiplier

        # Base target hazard weighting
        class_hazard_weights = {
            "ghost_net": 1.8,
            "fishing_gear": 1.7,
            "rope_cluster": 1.4,
            "metal_container": 1.5,
            "tire": 1.2,
            "plastic_debris": 1.3,
            "sunken_vessel": 2.0,
            "mine_hazard": 3.0,
            "debris": 1.2
        }
        cls_clean = target_class.lower().replace(" ", "_")
        base_weight = class_hazard_weights.get(cls_clean, 1.0)
        size_factor = min(2.0, max(1.0, math.sqrt(length_m * width_m) / 2.0))

        # Composite Risk Index (0.0 to 1.0)
        raw_risk = (confidence * 0.4) + (base_weight * 0.3) + (max_multiplier * 0.2) + (size_factor * 0.1)
        risk_index = min(1.0, max(0.0, raw_risk / 2.8))

        if risk_index >= 0.75 or any(o.get("sensitivity") == "CRITICAL" and o.get("intersection") for o in overlaps):
            risk_category = "CRITICAL"
            risk_score = "HIGH"
        elif risk_index >= 0.55 or len(overlaps) > 0:
            risk_category = "HIGH"
            risk_score = "HIGH"
        elif risk_index >= 0.35:
            risk_category = "MODERATE"
            risk_score = "MEDIUM"
        else:
            risk_category = "LOW"
            risk_score = "LOW"

        summary_parts = []
        if overlaps:
            top_ov = overlaps[0]
            if top_ov.get("intersection"):
                summary_parts.append(f"Direct intersection with {top_ov.get('name')} ({top_ov.get('type')}).")
            else:
                summary_parts.append(f"Within {top_ov.get('distance_m')}m of {top_ov.get('name')}.")
        if "net" in cls_clean or "gear" in cls_clean:
            summary_parts.append("Entanglement hazard to marine megafauna.")
        if not summary_parts:
            summary_parts.append("Isolated acoustic anomaly; low habitat interference.")

        return {
            "status": "COMPUTED",
            "risk_score": risk_score,
            "risk_category": risk_category,
            "overall_risk_index": round(risk_index, 3),
            "habitat_overlaps": overlaps,
            "nearest_infrastructure_m": round(nearest_infra_dist, 1) if nearest_infra_dist != float("inf") else None,
            "hazard_summary": " ".join(summary_parts)
        }

    def get_all_layers_geojson(self) -> Dict[str, Any]:
        """Returns consolidated GeoJSON feature collection for offline map rendering."""
        all_features = []
        for l_key, l_data in self.layers.items():
            for feat in l_data.get("features", []):
                f_copy = dict(feat)
                f_copy["properties"] = {
                    **f_copy.get("properties", {}),
                    "layer_key": l_key,
                    "layer_name": l_data.get("name", l_key)
                }
                all_features.append(f_copy)

        return {
            "type": "FeatureCollection",
            "name": "SeaSentinel_Local_Marine_GIS_Layers",
            "features": all_features
        }
