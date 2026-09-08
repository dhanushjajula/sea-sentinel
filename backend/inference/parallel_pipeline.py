"""
Parallel Dual-Path YOLO + U-Net Inference Engine
Executes independent Object Detection (YOLO) and Semantic Segmentation (U-Net)
concurrently using multi-threaded asynchronous execution.
Ensures zero coupling between models and resilient error isolation.
"""

from typing import Dict, Any, List, Optional, Tuple, Union
import time
import os
import concurrent.futures
import numpy as np

from ai.detection.yolo_detector import YOLODetector
from ai.segmentation.unet_segmenter import UNetSegmenter
from inference.tiled_inference import TiledInferenceEngine


class ParallelInferenceEngine:
    """
    Production-grade parallel execution engine running YOLO and U-Net concurrently.
    Neither model depends on the other.
    """
    def __init__(
        self,
        yolo_detector: Optional[YOLODetector] = None,
        unet_segmenter: Optional[UNetSegmenter] = None,
        tiling_engine: Optional[TiledInferenceEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.config = config or {}
        
        # Instantiate detectors if not injected
        yolo_cfg = self.config.get("yolo", {})
        unet_cfg = self.config.get("unet", {})
        tiling_cfg = self.config.get("tiling", {})

        self.yolo = yolo_detector or YOLODetector(
            model_path=yolo_cfg.get("model_path"),
            conf_thresh=yolo_cfg.get("conf_threshold", 0.25),
            iou_thresh=yolo_cfg.get("iou_threshold", 0.45),
            device=self.config.get("system", {}).get("device", "cpu")
        )

        self.unet = unet_segmenter or UNetSegmenter(
            checkpoint_path=unet_cfg.get("checkpoint_path"),
            model_type=unet_cfg.get("model_type", "attention_unet"),
            confidence_threshold=unet_cfg.get("confidence_threshold", 0.45),
            min_component_area_px=unet_cfg.get("min_component_area_px", 15),
            device=self.config.get("system", {}).get("device", "auto")
        )

        self.tiler = tiling_engine or TiledInferenceEngine(
            tile_size=tiling_cfg.get("tile_size", 640),
            overlap_ratio=tiling_cfg.get("overlap_ratio", 0.25),
            min_image_dim_for_tiling=tiling_cfg.get("min_image_dim_for_tiling", 900),
            nms_iou_threshold=tiling_cfg.get("nms_iou_threshold", 0.40)
        )

    def infer_yolo_path(
        self,
        image: np.ndarray,
        use_tiling_if_needed: bool = True
    ) -> Dict[str, Any]:
        """
        Executes YOLO object detection independently.
        """
        t0 = time.perf_counter()
        if image is None or image.size == 0:
            return {
                "status": "error",
                "source": "yolo",
                "error": "Empty or invalid image provided.",
                "detections": [],
                "inference_time_ms": 0.0
            }

        try:
            h, w = image.shape[:2]
            should_tile = use_tiling_if_needed and self.tiler.should_tile(image)

            if should_tile:
                raw_tiles = self.tiler.generate_tiles(image)
                active_tiles = self.tiler.filter_active_tiles(raw_tiles)
                
                all_raw_dets = []
                if active_tiles:
                    patch_list = [t["patch"] for t in active_tiles]
                    tile_ids = [t["tile_id"] for t in active_tiles]
                    batched_res = self.yolo.detect_batch(patch_list, tile_ids=tile_ids, batch_size=16)

                    for idx, t_res in enumerate(batched_res):
                        t_info = active_tiles[idx]
                        if t_res.get("detections"):
                            mapped = self.tiler.map_yolo_detections(
                                t_res["detections"],
                                offset_x=t_info["offset_x"],
                                offset_y=t_info["offset_y"],
                                max_w=w,
                                max_h=h
                            )
                            all_raw_dets.extend(mapped)

                merged_dets = self.tiler.merge_duplicate_boxes(all_raw_dets)
                inference_time_ms = round((time.perf_counter() - t0) * 1000, 2)
                return {
                    "status": "success",
                    "source": "yolo",
                    "tiled": True,
                    "tiles_count": len(raw_tiles),
                    "active_tiles_count": len(active_tiles),
                    "model_loaded": self.yolo.is_model_loaded,
                    "detections": merged_dets,
                    "total_detections": len(merged_dets),
                    "inference_time_ms": inference_time_ms
                }
            else:
                det_res = self.yolo.detect(image)
                inference_time_ms = round((time.perf_counter() - t0) * 1000, 2)
                return {
                    "status": det_res.get("status", "success"),
                    "source": "yolo",
                    "tiled": False,
                    "model_loaded": self.yolo.is_model_loaded,
                    "detections": det_res.get("detections", []),
                    "total_detections": len(det_res.get("detections", [])),
                    "inference_time_ms": inference_time_ms
                }
        except Exception as e:
            return {
                "status": "error",
                "source": "yolo",
                "error": str(e),
                "model_loaded": self.yolo.is_model_loaded,
                "detections": [],
                "total_detections": 0,
                "inference_time_ms": round((time.perf_counter() - t0) * 1000, 2)
            }

    def infer_unet_path(
        self,
        image: np.ndarray
    ) -> Dict[str, Any]:
        """
        Executes U-Net semantic segmentation and independent candidate extraction.
        """
        t0 = time.perf_counter()
        if image is None or image.size == 0:
            return {
                "status": "error",
                "source": "unet",
                "error": "Empty or invalid image provided.",
                "mask_available": False,
                "objects": [],
                "inference_time_ms": 0.0
            }

        try:
            seg_res = self.unet.segment_full_image(image)
            seg_res["source"] = "unet"
            return seg_res
        except Exception as e:
            h, w = image.shape[:2]
            return {
                "status": "error",
                "source": "unet",
                "error": str(e),
                "mask_available": False,
                "mask": np.zeros((h, w), dtype=np.uint8),
                "probability_map": np.zeros((h, w), dtype=np.float32),
                "objects": [],
                "total_objects": 0,
                "inference_time_ms": round((time.perf_counter() - t0) * 1000, 2)
            }

    def run_parallel_inference(
        self,
        image: np.ndarray,
        use_tiling_if_needed: bool = True
    ) -> Dict[str, Any]:
        """
        Runs YOLO and U-Net concurrently in a thread pool.
        """
        start_time = time.perf_counter()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_yolo = executor.submit(self.infer_yolo_path, image, use_tiling_if_needed)
            future_unet = executor.submit(self.infer_unet_path, image)

            yolo_result = future_yolo.result()
            unet_result = future_unet.result()

        total_parallel_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return {
            "yolo": yolo_result,
            "unet": unet_result,
            "total_parallel_ms": total_parallel_ms,
            "both_models_succeeded": (yolo_result.get("status") == "success" and unet_result.get("status") == "success")
        }
