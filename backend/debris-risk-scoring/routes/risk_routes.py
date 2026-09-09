"""Debris Risk Scoring API Routes."""
from fastapi import APIRouter
from pydantic import BaseModel
from backend.debris-risk-scoring.services.risk_engine_service import DebrisRiskScoringService

router = APIRouter(prefix="/debris-risk", tags=["Debris Risk Scoring"])
risk_service = DebrisRiskScoringService()

class RiskRequest(BaseModel):
    class_name: str
    confidence: float
    area_px: int

@router.post("/score")
def score_debris(req: RiskRequest):
    res = risk_service.calculate_risk(req.class_name, req.confidence, req.area_px)
    return {"status": "success", "risk": res}
