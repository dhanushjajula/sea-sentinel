"""Debris Density Routes."""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any
from backend.debris-density.services.density_service import DebrisDensityService

router = APIRouter(prefix="/debris-density", tags=["Debris Density"])

class DensityRequest(BaseModel):
    targets: List[Dict[str, Any]]
    swath_area_sq_m: float = 5000.0

@router.post("/estimate")
def estimate_density(req: DensityRequest):
    res = DebrisDensityService.calculate_density(req.targets, req.swath_area_sq_m)
    return {"status": "success", "density": res}
