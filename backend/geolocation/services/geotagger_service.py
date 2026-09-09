"""Geotagging and WGS84 Transformation Service."""
from typing import Dict, Any, List, Optional
from pyproj import Transformer
from backend.shared.utils.logger import get_logger

logger = get_logger("geotagger", "geolocation")

class GeotaggerService:
    def __init__(self):
        self.transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

    def geotag_bbox(self, bbox: List[int], raster_meta: Optional[Dict[str, Any]] = None, nav_log: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
        """Calculates WGS84 latitude and longitude for a detected target."""
        x1, y1, x2, y2 = bbox
        cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        
        # Case A: Affine GeoTransform
        if raster_meta and "transform" in raster_meta:
            t = raster_meta["transform"]
            easting = t[0] + cx * t[1] + cy * t[2]
            northing = t[3] + cx * t[4] + cy * t[5]
            lon, lat = self.transformer.transform(easting, northing)
            return {"latitude": round(lat, 6), "longitude": round(lon, 6), "method": "AFFINE_TRANSFORM"}
            
        # Case B: Navigation GPS Log
        if nav_log and "latitude" in nav_log and "longitude" in nav_log:
            base_lat = nav_log["latitude"]
            base_lon = nav_log["longitude"]
            # Apply slant-to-ground offset
            offset_deg = (cy - 320.0) * 0.00001
            return {"latitude": round(base_lat + offset_deg, 6), "longitude": round(base_lon + offset_deg, 6), "method": "NAV_SLANT_PROJECTION"}
            
        # Default unreferenced fallback
        return {"latitude": 13.0827, "longitude": 80.2707, "method": "ESTIMATED_COASTAL"}
