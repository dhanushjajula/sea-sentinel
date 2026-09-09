"""Geolocation API Routes."""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from backend.geolocation.services.geotagger_service import GeotaggerService

router = APIRouter(prefix="/geolocation", tags=["Geolocation"])
geotagger = GeotaggerService()

class GeotagRequest(BaseModel):
    bbox: List[int]
    raster_meta: Optional[Dict[str, Any]] = None
    nav_log: Optional[Dict[str, Any]] = None

@router.post("/tag")
def tag_target(req: GeotagRequest):
    coords = geotagger.geotag_bbox(req.bbox, req.raster_meta, req.nav_log)
    return {"status": "success", "coordinates": coords}
