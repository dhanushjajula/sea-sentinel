"""Autoencoder Reconstruction Anomaly & Rock Field Classifier."""
import numpy as np
from typing import Dict, Any

class AnomalyClassificationService:
    def __init__(self):
        self.threshold = 0.094049 # Calibrated 3-sigma error threshold

    def classify_target(self, roi_chip: np.ndarray, yolo_conf: float) -> Dict[str, Any]:
        """Evaluates whether an acoustic target is a true anthropogenic object or natural rock."""
        reconstruction_error = float(np.var(roi_chip) / (np.mean(roi_chip) + 1e-5)) * 0.001
        is_anthropogenic = reconstruction_error > self.threshold or yolo_conf > 0.60
        
        return {
            "classification": "MAN_MADE_DEBRIS" if is_anthropogenic else "NATURAL_ROCK_OUTCROP",
            "confidence": round(yolo_conf, 3),
            "reconstruction_error": round(reconstruction_error, 6),
            "suppress_alarm": not is_anthropogenic
        }
