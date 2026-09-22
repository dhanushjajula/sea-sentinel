"""Sonar Image Processing API Routes."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import cv2
<<<<<<< HEAD
from backend.sonar_image_processing.services.sonar_filter_service import SonarFilterService
=======
from backend.sonar-image-processing.services.sonar_filter_service import SonarFilterService
>>>>>>> 449ab6fff1827af49bd4a885932dc0cd8729161f

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
