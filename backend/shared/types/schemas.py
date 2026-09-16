"""Common Pydantic data schemas."""
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

class DebrisTarget(BaseModel):
    target_id: str
    class_name: str
    confidence: float
    bbox: List[int] = Field(description="[x1, y1, x2, y2]")
    area_px: Optional[int] = 0
    segmented_area_px: Optional[int] = 0
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    verification_status: Optional[str] = "VERIFIED"

class SurveyAnalysisResponse(BaseModel):
    status: str
    survey_id: str
    image_name: str
    targets_count: int
    targets: List[DebrisTarget]
    latency_ms: float
    report_url: Optional[str] = None
