"""
Tiled Inference Engine for Large Sonar Mosaics & GeoTIFFs
Provides overlapping sub-window tiling, coordinate translation to full image space,
and robust duplicate merging (NMS / Spatial Box Clustering).
"""

from typing import Dict, Any, List, Tuple, Optional
import time
import math
import numpy as np
import cv2


class TiledInferenceEngine:
    """
    Manages high-resolution tiled inference for large Side-Scan Sonar mosaics
    to prevent target destruction caused by aggressive downsampling.
    """
    def __init__(
        self,
        tile_size: int = 640,
        overlap_ratio: float = 0.25,
        min_image_dim_for_tiling: int = 900,
        nms_iou_threshold: float = 0.40
    ):
        self.tile_size = tile_size
        self.overlap_ratio = overlap_ratio
        self.min_image_dim_for_tiling = min_image_dim_for_tiling
        self.nms_iou_threshold = nms_iou_threshold

    def should_tile(self, image: np.ndarray) -> bool:
        """Determines if the image exceeds the tiling threshold."""
        if image is None:
            return False
        h, w = image.shape[:2]
        return max(h, w) >= self.min_image_dim_for_tiling

    def generate_tiles(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Splits image into overlapping tiles with boundary clamping.
        """
        if image is None:
            return []

        h, w = image.shape[:2]
        stride = int(self.tile_size * (1.0 - self.overlap_ratio))
        stride = max(32, stride)

        tiles = []
        tile_idx = 0

        y_starts = list(range(0, max(1, h - self.tile_size + 1), stride))
        if len(y_starts) == 0 or (y_starts[-1] + self.tile_size < h):
            y_starts.append(max(0, h - self.tile_size))

        x_starts = list(range(0, max(1, w - self.tile_size + 1), stride))
        if len(x_starts) == 0 or (x_starts[-1] + self.tile_size < w):
            x_starts.append(max(0, w - self.tile_size))

        for y in y_starts:
            for x in x_starts:
                x2 = min(w, x + self.tile_size)
                y2 = min(h, y + self.tile_size)
                patch = image[y:y2, x:x2]

                # Pad patch if at image boundaries and smaller than tile_size
                ph, pw = patch.shape[:2]
                if ph < self.tile_size or pw < self.tile_size:
                    if patch.ndim == 2:
                        padded = np.zeros((self.tile_size, self.tile_size), dtype=patch.dtype)
                        padded[:ph, :pw] = patch
                    else:
                        padded = np.zeros((self.tile_size, self.tile_size, patch.shape[2]), dtype=patch.dtype)
                        padded[:ph, :pw, :] = patch
                else:
                    padded = patch

                tile_id = f"TILE_{tile_idx:03d}"
                tiles.append({
                    "tile_id": tile_id,
                    "patch": padded,
                    "valid_w": pw,
                    "valid_h": ph,
                    "offset_x": x,
                    "offset_y": y,
                    "full_bounds": {"x1": x, "y1": y, "x2": x2, "y2": y2}
                })
                tile_idx += 1

        return tiles

    def filter_active_tiles(
        self,
        tiles: List[Dict[str, Any]],
        min_std_dev: float = 4.0
    ) -> List[Dict[str, Any]]:
        """
        Selectively filters out completely dead/zero-variance water column tiles,
        while preserving all tiles containing acoustic seafloor texture, highlights, or shadows.
        """
        if not tiles or len(tiles) <= 4:
            return tiles

        active_tiles = []
        for t in tiles:
            patch = t["patch"]
            # Fast standard deviation check
            std_val = float(np.std(patch))
            # Keep tile if there is any acoustic texture or variance
            if std_val >= min_std_dev:
                active_tiles.append(t)
            else:
                # Also check if max intensity is non-trivial (e.g. isolated highlight ping)
                max_val = float(np.max(patch))
                if max_val > 40:
                    active_tiles.append(t)

        # Fallback: if all were filtered, return original tiles to ensure safety
        return active_tiles if active_tiles else tiles

    def map_yolo_detections(
        self,
        tile_detections: List[Dict[str, Any]],
        offset_x: int,
        offset_y: int,
        max_w: int,
        max_h: int
    ) -> List[Dict[str, Any]]:
        """
        Translates detection bounding boxes from local tile coordinates to full-image coordinates.
        """
        mapped = []
        for d in tile_detections:
            tb = d.get("bbox", {})
            x1 = min(max_w, max(0.0, float(tb.get("x1", 0)) + offset_x))
            y1 = min(max_h, max(0.0, float(tb.get("y1", 0)) + offset_y))
            x2 = min(max_w, max(x1 + 1.0, float(tb.get("x2", 0)) + offset_x))
            y2 = min(max_h, max(y1 + 1.0, float(tb.get("y2", 0)) + offset_y))

            bw = round(x2 - x1, 1)
            bh = round(y2 - y1, 1)
            cx = round(x1 + bw / 2.0, 1)
            cy = round(y1 + bh / 2.0, 1)

            rec = dict(d)
            rec["bbox"] = {"x1": round(x1, 1), "y1": round(y1, 1), "x2": round(x2, 1), "y2": round(y2, 1)}
            rec["width"] = bw
            rec["height"] = bh
            rec["center"] = [cx, cy]
            rec["centroid"] = [cx, cy]
            mapped.append(rec)
        return mapped

    def merge_duplicate_boxes(
        self,
        detections: List[Dict[str, Any]],
        iou_thresh: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Merges duplicate bounding boxes from overlapping tiles using Non-Maximum Suppression (NMS).
        """
        if not detections:
            return []

        thresh = iou_thresh if iou_thresh is not None else self.nms_iou_threshold

        # Sort detections by confidence descending
        sorted_dets = sorted(detections, key=lambda d: d.get("confidence", 0.0), reverse=True)
        kept = []

        while sorted_dets:
            best = sorted_dets.pop(0)
            kept.append(best)

            remaining = []
            for d in sorted_dets:
                iou = self.calculate_box_iou(best.get("bbox", {}), d.get("bbox", {}))
                # Check centroid proximity as secondary check
                c1 = best.get("centroid", [0, 0])
                c2 = d.get("centroid", [0, 0])
                dist = math.hypot(c1[0] - c2[0], c1[1] - c2[1])

                b1 = best.get("bbox", {})
                diag = math.hypot(b1.get("x2", 0) - b1.get("x1", 0), b1.get("y2", 0) - b1.get("y1", 0))

                # If IoU exceeds threshold or centroids are extremely close within same class, merge
                if iou >= thresh or (dist < max(15.0, diag * 0.4) and best.get("class") == d.get("class")):
                    # Fuse confidence (keep maximum)
                    best["confidence"] = max(best.get("confidence", 0.0), d.get("confidence", 0.0))
                else:
                    remaining.append(d)

            sorted_dets = remaining

        # Re-index object IDs
        for idx, d in enumerate(kept):
            d["object_id"] = f"YOLO_{idx+1:03d}"

        return kept

    @staticmethod
    def calculate_box_iou(b1: Dict[str, float], b2: Dict[str, float]) -> float:
        """Calculates Intersection over Union (IoU) between two bounding boxes."""
        x1 = max(float(b1.get("x1", 0)), float(b2.get("x1", 0)))
        y1 = max(float(b1.get("y1", 0)), float(b2.get("y1", 0)))
        x2 = min(float(b1.get("x2", 0)), float(b2.get("x2", 0)))
        y2 = min(float(b1.get("y2", 0)), float(b2.get("y2", 0)))

        inter_w = max(0.0, x2 - x1)
        inter_h = max(0.0, y2 - y1)
        inter_area = inter_w * inter_h

        area1 = max(1.0, (float(b1.get("x2", 0)) - float(b1.get("x1", 0))) * (float(b1.get("y2", 0)) - float(b1.get("y1", 0))))
        area2 = max(1.0, (float(b2.get("x2", 0)) - float(b2.get("x1", 0))) * (float(b2.get("y2", 0)) - float(b2.get("y1", 0))))

        union_area = area1 + area2 - inter_area
        return float(inter_area / max(1.0, union_area))
