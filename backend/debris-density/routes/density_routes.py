"""Debris Density Routes."""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any
<<<<<<< HEAD
from backend.debris_density.services.density_service import DebrisDensityService
=======
from backend.debris-density.services.density_service import DebrisDensityService
>>>>>>> 449ab6fff1827af49bd4a885932dc0cd8729161f

router = APIRouter(prefix="/debris-density", tags=["Debris Density"])

class DensityRequest(BaseModel):
    targets: List[Dict[str, Any]]
    swath_area_sq_m: float = 5000.0

@router.post("/estimate")
def estimate_density(req: DensityRequest):
    res = DebrisDensityService.calculate_density(req.targets, req.swath_area_sq_m)
    return {"status": "success", "density": res}
