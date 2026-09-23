"""Sonar Image Processing API Routes."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import cv2
from backend.sonar_image_processing.services.sonar_filter_service import SonarFilterService

router = APIRouter(prefix="/sonar-processing", tags=["Sonar Image Processing"])

class ProcessRequest(BaseModel):
    image_path: str
    clip_limit: float = 2.5

@router.post("/enhance")
def enhance_image(req: ProcessRequest):
    try:
        img = cv2.imread(req.image_path)
        if img is None:
            raise HTTPException(status_code=404, detail="Image not found")
        enhanced = SonarFilterService.enhance(img, req.clip_limit)
        return {"status": "success", "shape": list(enhanced.shape)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
