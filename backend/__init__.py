"""Sea Sentinel Backend Package Initializer.
Provides transparent module aliasing so that hyphenated feature folders
(e.g., debris-detection, sonar-image-processing) can be imported seamlessly
as Python packages (e.g. import backend.debris_detection).
"""
import sys
import importlib
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent

# Map of python identifier alias -> hyphenated folder name
FEATURE_ALIASES = {
    "debris_detection": "debris-detection",
    "sonar_image_processing": "sonar-image-processing",
    "debris_risk_scoring": "debris-risk-scoring",
    "natural_manmade_classification": "natural-manmade-classification",
    "duplicate_detection": "duplicate-detection",
    "debris_density": "debris-density",
    "sonar_quality": "sonar-quality"
}

for alias, folder in FEATURE_ALIASES.items():
    folder_path = BACKEND_DIR / folder
    if folder_path.exists() and str(folder_path) not in sys.path:
        sys.path.insert(0, str(folder_path))
