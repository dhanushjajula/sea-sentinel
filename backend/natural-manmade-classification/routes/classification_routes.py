"""Natural vs Man-made API Routes."""
from fastapi import APIRouter
from pydantic import BaseModel
<<<<<<< HEAD
from backend.natural_manmade_classification.services.anomaly_service import AnomalyClassificationService
=======
from backend.natural-manmade-classification.services.anomaly_service import AnomalyClassificationService
>>>>>>> 449ab6fff1827af49bd4a885932dc0cd8729161f

router = APIRouter(prefix="/classification", tags=["Natural vs Man-Made"])
anomaly_service = AnomalyClassificationService()

class ClassifyRequest(BaseModel):
    confidence: float
    variance: float = 120.0

@router.post("/classify")
def classify(req: ClassifyRequest):
    is_manmade = req.confidence > 0.50
    return {
        "classification": "MAN_MADE_DEBRIS" if is_manmade else "NATURAL_ROCK_OUTCROP",
        "is_manmade": is_manmade
    }
