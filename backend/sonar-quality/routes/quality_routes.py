"""Sonar Quality Routes."""
from fastapi import APIRouter
from pydantic import BaseModel
from backend.sonar-quality.services.quality_service import SonarQualityService
import numpy as np

router = APIRouter(prefix="/sonar-quality", tags=["Sonar Quality"])

class QualityRequest(BaseModel):
    mean_backscatter: float = 75.0
    noise_variance: float = 22.0

@router.post("/evaluate")
def evaluate_quality(req: QualityRequest):
    enl = (req.mean_backscatter ** 2) / (req.noise_variance ** 2 + 1e-5)
    return {
        "status": "success",
        "equivalent_number_of_looks": round(enl, 2),
        "quality_rating": "OPTIMAL_SURVEY_GRADE" if enl > 6.0 else "MODERATE"
    }
