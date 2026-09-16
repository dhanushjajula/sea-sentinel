from fastapi import APIRouter

from backend.debris_detection.routes.detection_routes import router as detection_router
from backend.sonar_image_processing.routes.processing_routes import router as processing_router
from backend.geolocation.routes.geo_routes import router as geo_router
from backend.debris_risk_scoring.routes.risk_routes import router as risk_router
from backend.natural_manmade_classification.routes.classification_routes import router as classification_router
from backend.duplicate_detection.routes.duplicate_routes import router as duplicate_router
from backend.debris_density.routes.density_routes import router as density_router
from backend.sonar_quality.routes.quality_routes import router as quality_router
from backend.visualization.routes.viz_routes import router as viz_router

api_router = APIRouter(prefix="/api/v2")

api_router.include_router(detection_router)
api_router.include_router(processing_router)
api_router.include_router(geo_router)
api_router.include_router(risk_router)
api_router.include_router(classification_router)
api_router.include_router(duplicate_router)
api_router.include_router(density_router)
api_router.include_router(quality_router)
api_router.include_router(viz_router)
