"""FastAPI Routes for Debris Detection."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from backend.debris_detection.services.yolo_service import YoloDetectorService

router = APIRouter(prefix="/debris-detection", tags=["Debris Detection"])
detector = YoloDetectorService()

class DetectRequest(BaseModel):
    image_path: str
    conf_threshold: Optional[float] = 0.25

@router.post("/detect")
def detect_debris(req: DetectRequest):
    try:
        detections = detector.detect(req.image_path, req.conf_threshold)
        return {"status": "success", "count": len(detections), "detections": detections}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
