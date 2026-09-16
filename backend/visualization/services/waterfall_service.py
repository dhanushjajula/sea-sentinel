"""Sonar Waterfall Composite & Overlay Generator."""
import cv2
import numpy as np
from typing import List, Dict, Any

class VisualizationService:
    @staticmethod
    def render_overlay(raw_img: np.ndarray, detections: List[Dict[str, Any]], mask: np.ndarray = None) -> np.ndarray:
        rgb = cv2.cvtColor(raw_img, cv2.COLOR_GRAY2RGB) if len(raw_img.shape) == 2 else raw_img.copy()
        
        if mask is not None and mask.size > 0:
            overlay = rgb.copy()
            overlay[mask > 0] = [0, 255, 255] # Cyan / Yellow segmentation
            rgb = cv2.addWeighted(rgb, 0.70, overlay, 0.30, 0)
            
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            cv2.rectangle(rgb, (x1, y1), (x2, y2), (255, 50, 50), 2)
            lbl = f"{det['class_name']} ({det['confidence']:.2f})"
            cv2.putText(rgb, lbl, (x1, max(15, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 50, 50), 2)
            
        return rgb
