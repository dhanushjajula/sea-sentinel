"""
Stage 9: Production FastAPI REST API Server for Sea Sentinel
Ministry of Earth Sciences (MoES) — National Institute of Ocean Technology (NIOT)
Provides high-performance RESTful endpoints for:
  - Acoustic image & GeoTIFF upload
  - End-to-end AI Agent survey orchestration
  - Real-time geospatial target query (GeoJSON / CSV)
  - Historical audit retrieval from SQLite
  - System health diagnostics & model introspection
"""

from typing import Dict, Any, List, Optional
import os
import sys
import uuid
import json
import shutil
import sqlite3
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Ensure backend root is in python path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent.orchestrator import SIHPipelineAgent
from ai.geospatial.geotagger import GeospatialEngine

app = FastAPI(
    title="Sea Sentinel — AI Underwater Debris & Anomaly Detection API",
    description="MoES / NIOT Autonomous Side-Scan Sonar Debris Detection & Geotagging Engine",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for Frontend UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate Core Pipeline Agent & Geospatial Engine
agent = SIHPipelineAgent()
geotagger = GeospatialEngine()
CACHED_ANALYSES = {}

# Ensure Output and Static Directories
UPLOADS_DIR = os.path.join(PROJECT_ROOT, "outputs", "uploads")
PREPROCESSED_DIR = os.path.join(PROJECT_ROOT, "outputs", "preprocessed")
REPORTS_DIR = os.path.join(PROJECT_ROOT, "outputs", "reports")
SAMPLES_DIR = os.path.join(PROJECT_ROOT, "datasets", "samples")
FEEDBACK_CROPS_DIR = os.path.join(PROJECT_ROOT, "outputs", "feedback", "crops")
TEST_SAMPLES_DIR = os.path.join(PROJECT_ROOT, "datasets", "processed", "yolo_dataset", "images", "test")

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(PREPROCESSED_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(SAMPLES_DIR, exist_ok=True)
os.makedirs(FEEDBACK_CROPS_DIR, exist_ok=True)

# Mount Static File Routes
app.mount("/static/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")
app.mount("/static/preprocessed", StaticFiles(directory=PREPROCESSED_DIR), name="preprocessed")
app.mount("/static/feedback/crops", StaticFiles(directory=FEEDBACK_CROPS_DIR), name="feedback_crops")
if os.path.exists(SAMPLES_DIR):
    app.mount("/static/samples", StaticFiles(directory=SAMPLES_DIR), name="samples")


# -----------------------------------------------------------------
# Request & Response Schemas
# -----------------------------------------------------------------
class AnalyzeRequest(BaseModel):
    image_path: str
    raster_meta: Optional[Dict[str, Any]] = None
    nav_log: Optional[Dict[str, Any]] = None


class FeedbackRequest(BaseModel):
    analysis_id: str
    object_id: str
    comment: str
    corrected_class_override: Optional[str] = None


class TrainRequest(BaseModel):
    epochs: int = 5
    batch_size: int = 8
    device: str = "cpu"
    dry_run: bool = False


# -----------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------
@app.get("/")
def root():
    """System health, metadata, and operational status."""
    return {
        "system": "Sea Sentinel AI Pipeline",
        "organisation": "Ministry of Earth Sciences (MoES) — National Institute of Ocean Technology (NIOT)",
        "status": "OPERATIONAL",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "health": "/api/health",
            "samples": "/api/samples",
            "image": "/api/image?path=...",
            "upload": "POST /api/upload",
            "analyze": "POST /api/analyze",
            "results": "/api/results/{analysis_id}",
            "geospatial": "/api/geospatial",
            "high_risk": "/api/high-risk",
            "docs": "/docs"
        }
    }


@app.get("/api/health")
def health_check():
    """Introspects underlying computer vision, anomaly, and geospatial engines."""
    db_ok = os.path.exists(agent.audit_logger.db_path)
    return {
        "status": "healthy",
        "models": {
            "yolo_detector_loaded": agent.detector.is_model_loaded,
            "unet_segmenter_loaded": agent.segmenter.is_model_loaded,
            "autoencoder_loaded": agent.anomaly_detector.is_model_loaded,
            "baseline_threshold": agent.anomaly_detector.threshold
        },
        "geospatial": {
            "target_crs": geotagger.target_crs,
            "pyproj_available": True
        },
        "audit_database": {
            "path": agent.audit_logger.db_path,
            "connected": db_ok
        }
    }


@app.get("/api/samples")
def get_sample_missions():
    """Returns curated benchmark acoustic sonar scans for immediate 1-click survey analysis."""
    samples = [
        {
            "id": "noaa_h11584_gulf",
            "name": "NOAA Survey H11584 Mosaic (Gulf of Mexico)",
            "category": "georeferenced_mosaic",
            "risk_hint": "HIGH",
            "filename": "noaa_h11584_gulf_sample.tif",
            "description": "NOAA NOS Hydrographic Survey H11584 GeoTIFF mosaic in Gulf of Mexico (Mississippi/Alabama safety fairways). Authentic WGS84 UTM 16N coordinates (1.0m/px).",
            "path": os.path.join(SAMPLES_DIR, "noaa_h11584_gulf_sample.tif"),
            "url": "/static/samples/noaa_h11584_gulf_sample.tif",
            "georef_case": "A",
            "simulated_coords": {"lat": 30.171543, "lon": -87.823543}
        },
        {
            "id": "usgs_14bim05_breton",
            "name": "USGS DS 1005 Barrier Islands (Breton Sound LA)",
            "category": "georeferenced_mosaic",
            "risk_hint": "MEDIUM",
            "filename": "usgs_14bim05_breton_sample.tif",
            "description": "USGS DS 1005 high-resolution side-scan sonar mosaic near Breton & Gosier Islands, Louisiana. Authentic WGS84 UTM 16N coordinates (0.50m/px).",
            "path": os.path.join(SAMPLES_DIR, "usgs_14bim05_breton_sample.tif"),
            "url": "/static/samples/usgs_14bim05_breton_sample.tif",
            "georef_case": "A",
            "simulated_coords": {"lat": 29.425020, "lon": -89.193541}
        },
        {
            "id": "towfish_mission_case_b",
            "name": "Towfish Survey + Nav Telemetry (Case B)",
            "category": "sonar_waterfall",
            "risk_hint": "HIGH",
            "filename": "towfish_mission_case_b.png",
            "description": "Acoustic waterfall accompanied by navigation log (latitude, longitude, heading, altitude). Geodesic slant-to-ground range forward projection.",
            "path": os.path.join(SAMPLES_DIR, "towfish_mission_case_b.png"),
            "url": "/static/samples/towfish_mission_case_b.png",
            "georef_case": "B",
            "simulated_coords": {"lat": 30.193838, "lon": -87.880987}
        },
        {
            "id": "china_offshore_quanzhou_net",
            "name": "China Offshore SSS-AI (Zenodo 20048164)",
            "category": "fishing_net",
            "risk_hint": "HIGH",
            "filename": "china_offshore_quanzhou_net.jpg",
            "description": "Standardized cropped SSS image chip from Zenodo 20048164. Release contains image pixels only; no coordinates provided. Case C Unreferenced.",
            "path": os.path.join(SAMPLES_DIR, "china_offshore_quanzhou_net.jpg"),
            "url": "/static/samples/china_offshore_quanzhou_net.jpg",
            "georef_case": "C",
            "simulated_coords": None
        },
        {
            "id": "china_offshore_dongying_pipe",
            "name": "China Offshore SSS-AI Pipeline (Zenodo 20048164)",
            "category": "pipeline_or_cable",
            "risk_hint": "HIGH",
            "filename": "china_offshore_dongying_pipeline.jpg",
            "description": "Continuous linear acoustic signature from Zenodo 20048164. No telemetry provided in dataset; coordinates are strictly withheld.",
            "path": os.path.join(SAMPLES_DIR, "china_offshore_dongying_pipeline.jpg"),
            "url": "/static/samples/china_offshore_dongying_pipeline.jpg",
            "georef_case": "C",
            "simulated_coords": None
        }
    ]
    valid_samples = [s for s in samples if os.path.exists(s["path"])]
    return {
        "status": "success",
        "total_samples": len(valid_samples),
        "samples": valid_samples
    }


import cv2
import numpy as np


@app.get("/api/image")
def get_image_file(path: str = Query(...)):
    """Safely streams image files to the frontend UI, converting TIFF/GeoTIFF to PNG for browser compatibility."""
    real_path = os.path.abspath(path)
    if not real_path.lower().startswith(PROJECT_ROOT.lower()):
        raise HTTPException(status_code=403, detail="Access denied: path outside project root.")
    if not os.path.exists(real_path):
        raise HTTPException(status_code=404, detail="Image file not found.")

    ext = os.path.splitext(real_path)[1].lower()

    # If the image is a TIFF/GeoTIFF, modern web browsers cannot render it natively.
    # Convert on-the-fly to a standard PNG stream for instant high-quality browser rendering.
    if ext in [".tif", ".tiff"]:
        import hashlib
        mtime = os.path.getmtime(real_path)
        cache_key = hashlib.md5(f"{real_path}_{mtime}".encode()).hexdigest()
        cached_png = os.path.join(PREPROCESSED_DIR, f"cached_tiff_{cache_key}.png")
        if os.path.exists(cached_png):
            return FileResponse(cached_png, media_type="image/png")

        img = None
        try:
            img = cv2.imread(real_path, cv2.IMREAD_UNCHANGED)
        except Exception:
            img = None

        if img is None:
            try:
                from PIL import Image
                Image.MAX_IMAGE_PIXELS = None
                with Image.open(real_path) as pil_im:
                    w, h = pil_im.size
                    max_dim = 2048
                    if max(w, h) > max_dim:
                        scale = max_dim / float(max(w, h))
                        pil_im = pil_im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.BILINEAR)
                    img = np.array(pil_im.convert("L"))
            except Exception:
                pass

        if img is not None:
            if img.dtype != np.uint8:
                img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
            try:
                cv2.imwrite(cached_png, img)
                return FileResponse(cached_png, media_type="image/png")
            except Exception:
                success, encoded = cv2.imencode(".png", img)
                if success:
                    return Response(content=encoded.tobytes(), media_type="image/png")

    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".bmp": "image/bmp"
    }
    return FileResponse(real_path, media_type=media_types.get(ext, "image/jpeg"))


@app.post("/api/upload")
async def upload_sonar_file(file: UploadFile = File(...)):
    """
    Uploads raw sonar imagery, GeoTIFF rasters, or waterfall scans.
    """
    allowed_exts = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_exts:
        raise HTTPException(status_code=400, detail=f"Unsupported file format: {ext}")

    file_id = str(uuid.uuid4())[:8]
    safe_name = f"{file_id}_{os.path.basename(file.filename)}"
    destination = os.path.join(UPLOADS_DIR, safe_name)

    with open(destination, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    val_res = agent.preprocessor.validate_image(destination)
    if not val_res.get("valid"):
        try:
            if os.path.exists(destination):
                os.remove(destination)
        except Exception:
            pass
        reason_msg = val_res.get("reason") or val_res.get("error") or "Invalid Input: The uploaded file is not an authentic Side-Scan Sonar (SSS) acoustic image."
        raise HTTPException(
            status_code=400,
            detail=reason_msg
        )

    raster_meta = geotagger.read_raster_metadata(destination)
    georef_case = geotagger.classify_georef_case(raster_meta)

    return {
        "status": "uploaded",
        "filename": file.filename,
        "saved_path": destination,
        "size_bytes": os.path.getsize(destination),
        "valid_image": True,
        "is_sonar": True,
        "georeferencing_case": georef_case,
        "raster_metadata": raster_meta,
        "image_url": f"/static/uploads/{safe_name}"
    }


@app.post("/api/analyze")
def analyze_survey(req: AnalyzeRequest):
    """
    Executes end-to-end AI Agent survey analysis on the given sonar image.
    """
    if not os.path.exists(req.image_path):
        raise HTTPException(status_code=404, detail=f"Image not found at: {req.image_path}")

    res = agent.analyze_image(
        image_path=req.image_path,
        raster_meta_override=req.raster_meta,
        nav_log=req.nav_log
    )

    if res.get("status") == "rejected":
        raise HTTPException(
            status_code=400,
            detail=res.get("error") or "Analysis rejected: The input is not an authentic Side-Scan Sonar (SSS) acoustic image."
        )

    # Attach convenient relative URLs for frontend display
    analysis_id = res.get("analysis_id", "")
    raw_p = res.get("raw_image_path")
    if raw_p and os.path.exists(raw_p):
        res["raw_image_url"] = f"/static/preprocessed/{os.path.basename(raw_p)}"
    else:
        res["raw_image_url"] = f"/api/image?path={os.path.abspath(req.image_path)}"
    
    enhanced_p = res.get("enhanced_image_path")
    if enhanced_p and os.path.exists(enhanced_p):
        res["enhanced_image_url"] = f"/static/preprocessed/{os.path.basename(enhanced_p)}"

    annotated_p = res.get("annotated_image_path")
    if annotated_p and os.path.exists(annotated_p):
        res["annotated_image_url"] = f"/static/preprocessed/{os.path.basename(annotated_p)}"

    # Cache for report endpoints
    CACHED_ANALYSES[analysis_id] = res
    CACHED_ANALYSES["latest"] = res

    return res


@app.get("/api/results/{analysis_id}")
def get_survey_results(analysis_id: str):
    """
    Retrieves historical survey session results from the SQLite audit database.
    """
    summary = agent.audit_logger.get_session_summary(analysis_id)
    if not summary:
        raise HTTPException(status_code=404, detail=f"Survey session {analysis_id} not found in audit logs.")
    return summary


@app.get("/api/geospatial")
def get_geospatial_targets(limit: int = Query(200, ge=1, le=1000)):
    """
    Returns all georeferenced subsea targets as a standard GeoJSON FeatureCollection.
    """
    conn = sqlite3.connect(agent.audit_logger.db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM target_detections
            WHERE lat IS NOT NULL AND lon IS NOT NULL
            ORDER BY calibrated_confidence DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        targets = []
        for r in rows:
            d = dict(r)
            d["latitude"] = d.get("lat")
            d["longitude"] = d.get("lon")
            targets.append(d)
    finally:
        conn.close()

    features = []
    for t in targets:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [t["lon"], t["lat"]]
            },
            "properties": {k: v for k, v in t.items() if k not in ("lat", "lon", "latitude", "longitude")}
        })

    return {
        "type": "FeatureCollection",
        "total_targets": len(features),
        "features": features,
        "targets": targets
    }


@app.get("/api/high-risk")
def get_high_risk_targets(limit: int = Query(50, ge=1, le=200)):
    """
    Queries high-priority targets flagged as HIGH hazard risk.
    """
    targets = agent.audit_logger.query_high_risk_targets(limit=limit)
    return {
        "count": len(targets),
        "high_risk_targets": targets
    }


@app.get("/api/report/{analysis_id}/csv")
def download_survey_csv(analysis_id: str):
    """
    Exports and downloads tabular hydrographic CSV for a survey session.
    """
    summary = agent.audit_logger.get_session_summary(analysis_id)
    if not summary:
        raise HTTPException(status_code=404, detail=f"Survey session {analysis_id} not found.")

    csv_path = os.path.join(REPORTS_DIR, f"{analysis_id}_survey.csv")
    geotagger.export_csv(summary.get("targets", []), csv_path)

    if not os.path.exists(csv_path):
        raise HTTPException(status_code=500, detail="Failed to generate CSV export.")

    return FileResponse(
        csv_path,
        media_type="text/csv",
        filename=f"{analysis_id}_hydrographic_report.csv"
    )


# -----------------------------------------------------------------
# Human Feedback & Continuous Learning Endpoints
# -----------------------------------------------------------------
@app.post("/api/feedback")
def submit_feedback(req: FeedbackRequest):
    """
    Submits natural language human feedback for a YOLO11 detection:
      1. Parses natural language comment using FeedbackNLUEngine.
      2. Extracts crop and stores acoustic signature in SQLite CorrectionMemory.
      3. Automatically writes normalized training sample to YOLOv11 dataset directory.
      4. Hot-updates cached target in memory for instant UI reflection.
    """
    if not req.comment or not req.comment.strip():
        raise HTTPException(status_code=400, detail="Comment cannot be empty.")

    # Locate survey data
    analysis = CACHED_ANALYSES.get(req.analysis_id)
    if not analysis:
        if req.analysis_id == "latest" and CACHED_ANALYSES:
            analysis = CACHED_ANALYSES.get("latest")
        else:
            summary = agent.audit_logger.get_session_summary(req.analysis_id)
            if not summary:
                raise HTTPException(status_code=404, detail=f"Survey session '{req.analysis_id}' not found.")
            analysis = summary

    # Locate target
    targets = analysis.get("detections") or analysis.get("targets") or []
    target = next((t for t in targets if str(t.get("object_id")) == str(req.object_id)), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Target '{req.object_id}' not found in survey '{req.analysis_id}'.")

    # Run NLU parser
    orig_class = target.get("class", "unknown")
    nlu_result = agent.nlu_engine.parse_feedback(
        text=req.comment,
        original_class=orig_class
    )
    if req.corrected_class_override and req.corrected_class_override in agent.nlu_engine.CLASS_NAME_TO_ID:
        nlu_result["corrected_class"] = req.corrected_class_override
        nlu_result["corrected_class_id"] = agent.nlu_engine.CLASS_NAME_TO_ID[req.corrected_class_override]

    # Resolve image source & full image
    img_path = analysis.get("image_path") or analysis.get("raw_image_path")
    if not img_path or not os.path.exists(img_path):
        candidate_raw = os.path.join(PREPROCESSED_DIR, f"{analysis.get('analysis_id', req.analysis_id)}_raw.png")
        if os.path.exists(candidate_raw):
            img_path = candidate_raw

    full_img = None
    bbox = target.get("bbox", {})
    if img_path and os.path.exists(img_path):
        try:
            full_img = cv2.imread(img_path, cv2.IMREAD_UNCHANGED)
        except Exception:
            full_img = None

    if full_img is None:
        full_img = np.zeros((256, 256), dtype=np.uint8)
        bbox = {"x1": 32, "y1": 32, "x2": 96, "y2": 96}

    # Save to Correction Memory
    mem_entry = agent.correction_memory.save_correction(
        source_image=full_img if img_path is None else img_path,
        bbox=bbox,
        original_class=orig_class,
        corrected_class=nlu_result["corrected_class"],
        corrected_class_id=nlu_result["corrected_class_id"],
        human_comment=req.comment,
        extracted_reason=nlu_result.get("rationale", "User feedback"),
        correction_type=nlu_result.get("correction_type", "reclassify"),
        original_confidence=float(target.get("calibrated_confidence") or target.get("confidence") or 0.5),
        session_id=analysis.get("analysis_id", req.analysis_id),
        object_id=req.object_id
    )

    # Accumulate into YOLO dataset if valid class (not false_alarm)
    dataset_entry = None
    if nlu_result.get("corrected_class") != "false_alarm" and nlu_result.get("corrected_class_id") is not None and nlu_result.get("corrected_class_id") >= 0:
        try:
            dataset_entry = agent.dataset_accumulator.add_correction_sample(
                feedback_id=mem_entry["feedback_id"],
                image_input=full_img if img_path is None else img_path,
                bbox=bbox,
                class_id=nlu_result["corrected_class_id"]
            )
        except Exception as e:
            print(f"[Feedback API] Dataset accumulation error: {e}")

    # Hot-update target in-place
    target["original_model_class"] = orig_class
    target["class"] = nlu_result["corrected_class"]
    target["class_id"] = nlu_result["corrected_class_id"]
    target["memory_corrected"] = True
    target["human_feedback"] = {
        "feedback_id": mem_entry["feedback_id"],
        "comment": req.comment,
        "rationale": nlu_result.get("rationale"),
        "confidence": nlu_result.get("confidence"),
        "crop_url": mem_entry.get("crop_url")
    }

    if "explanation" in target and isinstance(target["explanation"], dict):
        target["explanation"]["executive_narrative"] = (
            f"Human Correction Applied: Reclassified from '{orig_class}' to '{nlu_result['corrected_class']}' "
            f"via operator feedback (Reason: {nlu_result.get('rationale', 'User specified correction')})."
        )

    if "stats" in analysis:
        analysis["stats"]["memory_corrected_count"] = sum(1 for d in targets if d.get("memory_corrected"))

    return {
        "status": "success",
        "message": f"Feedback applied: '{orig_class}' -> '{nlu_result['corrected_class']}'",
        "feedback_id": mem_entry["feedback_id"],
        "crop_url": mem_entry.get("crop_url"),
        "original_class": orig_class,
        "corrected_class": nlu_result["corrected_class"],
        "corrected_class_id": nlu_result["corrected_class_id"],
        "rationale": nlu_result.get("rationale"),
        "nlu_confidence": nlu_result.get("confidence"),
        "dataset_sample_added": dataset_entry is not None,
        "target": target
    }


@app.get("/api/feedback/memory")
def get_feedback_memory(limit: int = Query(50, ge=1, le=500)):
    """Retrieves list of accumulated human corrections and memory statistics."""
    corrections = agent.correction_memory.get_recent_corrections(limit=limit)
    mem_stats = agent.correction_memory.get_stats()
    ds_stats = agent.dataset_accumulator.get_dataset_stats()
    train_status = agent.learner.get_status()
    return {
        "status": "success",
        "stats": {
            **mem_stats,
            **ds_stats,
            "training_status": train_status
        },
        "corrections": corrections
    }


@app.post("/api/feedback/train")
def trigger_fine_tuning(req: Optional[TrainRequest] = None):
    """Triggers periodic YOLO11 transfer learning fine-tuning on accumulated human corrections."""
    epochs = req.epochs if req else 5
    batch = req.batch_size if req else 8
    dev = req.device if req else "cpu"
    dry = req.dry_run if req else False

    ds_stats = agent.dataset_accumulator.get_dataset_stats()
    if not ds_stats.get("ready_for_fine_tuning") and not dry:
        return {
            "status": "insufficient_data",
            "message": "No accumulated feedback samples yet. Submit at least one correction or set dry_run=True.",
            "dataset_stats": ds_stats
        }

    res = agent.learner.start_background_training(
        data_yaml=agent.dataset_accumulator.data_yaml_path,
        epochs=epochs,
        batch_size=batch,
        device=dev,
        dry_run=dry
    )
    return res


@app.get("/api/feedback/status")
def get_learner_status():
    """Checks continuous training and model hot-reload status."""
    return agent.learner.get_status()


@app.get("/api/report/{analysis_id}")
def get_survey_report_data(analysis_id: str):
    """
    Returns structured survey mission report containing image classification, confidence scores,
    priority levels (>75% HIGHER, <=75% LOWER), all candidate classes, coordinates, and physical dimensions.
    """
    data = CACHED_ANALYSES.get(analysis_id)
    if not data:
        if analysis_id == "latest" and CACHED_ANALYSES:
            data = CACHED_ANALYSES.get("latest")
        else:
            summary = agent.audit_logger.get_session_summary(analysis_id)
            if not summary:
                raise HTTPException(status_code=404, detail=f"Survey session {analysis_id} not found.")
            data = summary

    report_summary = data.get("report_summary")
    if not report_summary:
        targets = data.get("detections") or data.get("targets") or []
        best_t = max(targets, key=lambda x: x.get("calibrated_confidence") or x.get("confidence") or 0.0, default={})
        conf = float(best_t.get("calibrated_confidence") or best_t.get("confidence") or 0.0)
        prio = "HIGHER" if conf > 0.75 else "LOWER"
        report_summary = {
            "obtained_image_class": best_t.get("class", "unclassified_debris"),
            "confidence_score": round(conf, 3),
            "confidence_pct": round(conf * 100, 1),
            "priority_level": prio,
            "priority_label": f"{prio} PRIORITY ({'> 75%' if prio == 'HIGHER' else '<= 75%'})",
            "candidate_classes_breakdown": best_t.get("all_detected_classes", []),
            "spatial_location": {
                "latitude": best_t.get("latitude"),
                "longitude": best_t.get("longitude"),
                "total_area_sq_m": best_t.get("area_sq_m"),
                "max_length_m": best_t.get("length_m"),
                "max_width_m": best_t.get("width_m")
            }
        }

    return {
        "analysis_id": analysis_id,
        "status": "success",
        "timestamp": datetime.utcnow().isoformat(),
        "report_summary": report_summary,
        "detections": data.get("detections") or data.get("targets") or [],
        "raw_image_url": data.get("raw_image_url"),
        "enhanced_image_url": data.get("enhanced_image_url"),
        "annotated_image_url": data.get("annotated_image_url"),
        "georeferencing_case": data.get("georeferencing_case", "A")
    }


@app.get("/api/report/{analysis_id}/html", response_class=HTMLResponse)
def get_survey_report_html(analysis_id: str):
    """
    Renders a publication-ready, printable Hydrographic Survey Mission Report.
    """
    report_data = get_survey_report_data(analysis_id)
    rep = report_data.get("report_summary", {})
    prio_level = rep.get("priority_level", "LOWER")
    prio_color = "#ef4444" if prio_level == "HIGHER" else "#0284c7"
    prio_badge = f'<span style="background: {prio_color}; color: #ffffff; padding: 6px 14px; border-radius: 9999px; font-weight: 700; font-size: 0.85rem; letter-spacing: 0.5px; text-transform: uppercase;">▲ HIGHER PRIORITY (&gt; 75%)</span>' if prio_level == "HIGHER" else f'<span style="background: {prio_color}; color: #ffffff; padding: 6px 14px; border-radius: 9999px; font-weight: 700; font-size: 0.85rem; letter-spacing: 0.5px; text-transform: uppercase;">▼ LOWER PRIORITY (≤ 75%)</span>'

    spatial = rep.get("spatial_location", {})
    lat = spatial.get("latitude")
    lon = spatial.get("longitude")
    has_coords = lat is not None and lon is not None
    lat_str = f"{lat:.6f}° N" if lat is not None else "Unreferenced (Case C)"
    lon_str = f"{abs(lon):.6f}° {'W' if lon and lon < 0 else 'E'}" if lon is not None else "Unreferenced"
    len_m = spatial.get("max_length_m") or "Estimated"
    wid_m = spatial.get("max_width_m") or "Estimated"
    area_m = spatial.get("total_area_sq_m") or "Estimated"

    raw_img = report_data.get("raw_image_url") or "/static/uploads/default.png"
    annot_img = report_data.get("annotated_image_url") or report_data.get("enhanced_image_url") or raw_img

    # Candidates table
    candidates_html = ""
    for c in rep.get("candidate_classes_breakdown", []):
        c_prio = c.get("priority_level", "LOWER")
        c_badge = '<span style="color: #ef4444; font-weight: 700;">HIGHER (&gt;75%)</span>' if c_prio == "HIGHER" else '<span style="color: #64748b; font-weight: 600;">LOWER (≤75%)</span>'
        candidates_html += f"""
        <tr style="border-bottom: 1px solid #e2e8f0;">
          <td style="padding: 10px 12px; font-weight: 600; text-transform: capitalize;">{c.get('class', '').replace('_', ' ')}</td>
          <td style="padding: 10px 12px; font-family: monospace; font-size: 1rem;">{c.get('confidence_pct', 0)}%</td>
          <td style="padding: 10px 12px;">{c_badge}</td>
        </tr>
        """

    # Target table
    targets_html = ""
    for idx, t in enumerate(report_data.get("detections", [])):
        t_conf = round(float(t.get("calibrated_confidence") or t.get("confidence") or 0.0) * 100, 1)
        t_prio = "HIGHER" if t_conf > 75.0 else "LOWER"
        t_prio_badge = '<span style="color: #ef4444; font-weight: 700;">HIGHER</span>' if t_prio == "HIGHER" else '<span style="color: #64748b; font-weight: 600;">LOWER</span>'
        t_coords = f"{t.get('latitude', 0):.5f}, {t.get('longitude', 0):.5f}" if t.get('latitude') else "Unreferenced"
        t_dims = f"{t.get('length_m', '-')}m × {t.get('width_m', '-')}m"
        targets_html += f"""
        <tr style="border-bottom: 1px solid #e2e8f0;">
          <td style="padding: 8px 10px; font-weight: 600; font-family: monospace;">{t.get('object_id', f'TGT_{idx+1:03d}')}</td>
          <td style="padding: 8px 10px; text-transform: capitalize;">{t.get('class', '').replace('_', ' ')}</td>
          <td style="padding: 8px 10px; font-family: monospace;">{t_conf}%</td>
          <td style="padding: 8px 10px;">{t_prio_badge}</td>
          <td style="padding: 8px 10px; font-family: monospace; font-size: 0.85rem;">{t_coords}</td>
          <td style="padding: 8px 10px; font-size: 0.85rem;">{t_dims}</td>
          <td style="padding: 8px 10px; font-size: 0.85rem;">{t.get('anomaly_status', 'evaluated')}</td>
        </tr>
        """

    map_lat = lat if has_coords else 42.7474
    map_lon = lon if has_coords else -73.7945

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Hydrographic Mission Report — {analysis_id}</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      margin: 0;
      padding: 30px;
      background: #f8fafc;
      color: #0f172a;
      line-height: 1.5;
    }}
    .report-card {{
      max-width: 1040px;
      margin: 0 auto;
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 36px 44px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      border-bottom: 2px solid #0f172a;
      padding-bottom: 18px;
      margin-bottom: 26px;
    }}
    .header-sub {{
      font-size: 0.78rem;
      letter-spacing: 0.8px;
      text-transform: uppercase;
      font-weight: 700;
      color: #0369a1;
      margin-bottom: 4px;
    }}
    .header-title {{
      font-size: 1.6rem;
      font-weight: 800;
      color: #0f172a;
      margin: 0;
    }}
    .grid-2 {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
      margin-bottom: 24px;
    }}
    .stat-card {{
      background: #f1f5f9;
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      padding: 16px 20px;
    }}
    .section-title {{
      font-size: 1.1rem;
      font-weight: 700;
      color: #0f172a;
      border-bottom: 1px solid #e2e8f0;
      padding-bottom: 8px;
      margin-top: 24px;
      margin-bottom: 16px;
    }}
    .img-box {{
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      overflow: hidden;
      background: #000;
      text-align: center;
    }}
    .img-box img {{
      max-width: 100%;
      height: auto;
      max-height: 280px;
      display: block;
      margin: 0 auto;
    }}
    .img-label {{
      background: #0f172a;
      color: #ffffff;
      font-size: 0.75rem;
      padding: 6px;
      font-weight: 600;
      letter-spacing: 0.5px;
    }}
    #map {{
      height: 320px;
      width: 100%;
      border-radius: 8px;
      border: 1px solid #cbd5e1;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.9rem;
    }}
    th {{
      background: #0f172a;
      color: #ffffff;
      padding: 10px;
      text-align: left;
      font-weight: 600;
      font-size: 0.8rem;
      letter-spacing: 0.5px;
    }}
    .btn-print {{
      background: #0f172a;
      color: #ffffff;
      border: none;
      padding: 10px 20px;
      border-radius: 6px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      text-decoration: none;
    }}
    .btn-print:hover {{ background: #1e293b; }}
    @media print {{
      body {{ background: #fff; padding: 0; }}
      .report-card {{ border: none; box-shadow: none; padding: 0; }}
      .no-print {{ display: none !important; }}
    }}
  </style>
</head>
<body>

  <div class="report-card">
    <div class="header">
      <div>
        <div class="header-sub">Ministry of Earth Sciences (MoES) — National Institute of Ocean Technology (NIOT)</div>
        <h1 class="header-title">Autonomous Hydrographic Survey Mission Report</h1>
        <div style="font-size: 0.85rem; color: #64748b; margin-top: 4px;">
          Mission ID: <b>{analysis_id}</b> | Generated: <b>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</b>
        </div>
      </div>
      <div class="no-print">
        <button class="btn-print" onclick="window.print()">🖨️ Print / Save PDF</button>
      </div>
    </div>

    <!-- Rule Callout -->
    <div style="background: #e0f2fe; border-left: 4px solid #0284c7; padding: 12px 16px; border-radius: 4px; margin-bottom: 22px; font-size: 0.88rem;">
      <b>Evaluation Priority Standard:</b> Target confidence score <b>&gt; 75.0%</b> is categorized as <b>HIGHER PRIORITY</b> (Immediate intervention/inspection); confidence score <b>≤ 75.0%</b> is categorized as <b>LOWER PRIORITY</b> (Passive seabed monitoring).
    </div>

    <!-- Obtained Classification & Priority Banner -->
    <div class="grid-2">
      <div class="stat-card" style="border-left: 5px solid {prio_color};">
        <div style="font-size: 0.75rem; text-transform: uppercase; font-weight: 700; color: #64748b; margin-bottom: 4px;">Obtained Primary Image Class</div>
        <div style="font-size: 1.6rem; font-weight: 800; text-transform: capitalize; color: #0f172a;">{rep.get('obtained_image_class', 'N/A').replace('_', ' ')}</div>
        <div style="margin-top: 8px; display: flex; align-items: center; gap: 12px;">
          <span style="font-size: 1.1rem; font-weight: 700; color: #0f172a;">Confidence: {rep.get('confidence_pct', 0)}%</span>
          {prio_badge}
        </div>
      </div>

      <div class="stat-card">
        <div style="font-size: 0.75rem; text-transform: uppercase; font-weight: 700; color: #64748b; margin-bottom: 4px;">Geospatial Survey Location & Dimensions</div>
        <div style="font-size: 0.95rem; font-weight: 600; margin-bottom: 3px;">
          <b>Latitude:</b> <span style="font-family: monospace;">{lat_str}</span>
        </div>
        <div style="font-size: 0.95rem; font-weight: 600; margin-bottom: 6px;">
          <b>Longitude:</b> <span style="font-family: monospace;">{lon_str}</span>
        </div>
        <div style="font-size: 0.85rem; color: #475569;">
          <b>Physical Dimensions:</b> {len_m}m (Length) × {wid_m}m (Width) | <b>Area:</b> {area_m} m²
        </div>
      </div>
    </div>

    <!-- Multi-Class Candidate Confidence Breakdown -->
    <div class="section-title">Detected Classes & Confidence Distribution</div>
    <table>
      <thead>
        <tr>
          <th>Detected Debris Class</th>
          <th>Confidence Score</th>
          <th>Operational Priority Threshold</th>
        </tr>
      </thead>
      <tbody>
        {candidates_html}
      </tbody>
    </table>

    <!-- Sonar Imagery Section -->
    <div class="section-title">Sonar Imagery Analysis (Input vs Processed)</div>
    <div class="grid-2">
      <div class="img-box">
        <div class="img-label">INPUT RAW ACOUSTIC SONAR SCAN</div>
        <img src="{raw_img}" alt="Input Sonar Scan" />
      </div>
      <div class="img-box">
        <div class="img-label">AI PROCESSED & ANNOTATED DETECTIONS</div>
        <img src="{annot_img}" alt="Annotated Sonar Scan" />
      </div>
    </div>

    <!-- Location Map Section -->
    <div class="section-title">Georeferenced Survey Location Map (WGS84)</div>
    <div id="map"></div>
    <div style="font-size: 0.8rem; color: #64748b; margin-top: 6px;">
      Georeferencing Datum: <b>WGS84 (EPSG:4326)</b> | Survey Coordinates: <b>{lat_str}, {lon_str}</b> | Basemap: <b>ESRI World Dark Canvas</b>
    </div>

    <!-- Target Inventory Table -->
    <div class="section-title">Comprehensive Target Inventory ({len(report_data.get('detections', []))} Objects)</div>
    <table>
      <thead>
        <tr>
          <th>Target ID</th>
          <th>Class</th>
          <th>Confidence</th>
          <th>Priority</th>
          <th>WGS84 Coordinates</th>
          <th>Dimensions</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {targets_html}
      </tbody>
    </table>

    <div style="margin-top: 36px; padding-top: 16px; border-top: 1px solid #cbd5e1; font-size: 0.78rem; color: #94a3b8; display: flex; justify-content: space-between;">
      <span>Sea Sentinel Hydrographic Platform — NIOT / MoES Verification Audit</span>
      <span>Classification Standard: Confidence &gt; 75% = HIGHER PRIORITY</span>
    </div>
  </div>

  <script>
    const map = L.map('map', {{ center: [{map_lat}, {map_lon}], zoom: 14, zoomControl: true }});
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
      attribution: '&copy; Esri &mdash; NIOT Sea Sentinel'
    }}).addTo(map);

    const marker = L.marker([{map_lat}, {map_lon}]).addTo(map);
    marker.bindPopup("<b>{rep.get('obtained_image_class', 'Debris Target').replace('_', ' ').title()}</b><br>Confidence: {rep.get('confidence_pct', 0)}%<br>Priority: {prio_level} PRIORITY<br>Coords: {lat_str}, {lon_str}").openPopup();
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)
