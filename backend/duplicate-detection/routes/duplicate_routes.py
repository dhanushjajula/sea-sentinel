"""Duplicate Detection Routes."""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any
from backend.duplicate-detection.services.multiframe_tracker import MultiFrameTrackerService

router = APIRouter(prefix="/duplicate-detection", tags=["Duplicate Detection"])
tracker = MultiFrameTrackerService()

class TrackRequest(BaseModel):
    frame_idx: int
    detections: List[Dict[str, Any]]

@router.post("/track")
def track_targets(req: TrackRequest):
    results = tracker.process_frame(req.frame_idx, req.detections)
    return {"status": "success", "tracked_targets": results}
