"""
Adaptive Dataset Management & Anti-Forgetting Replay Subsystem for Sea Sentinel.
Curates versioned training sets blending baseline acoustic imagery, hard negatives,
verified human corrections, and historical error samples to prevent catastrophic forgetting.
"""

from typing import Dict, Any, List, Optional
import os
import shutil
import yaml
import json
import numpy as np
import cv2
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATASETS_BASE = os.path.join(PROJECT_ROOT, "backend", "datasets", "learning_versions")
BASE_YOLO_DATASET = os.path.join(PROJECT_ROOT, "backend", "datasets", "processed", "yolo_dataset")
os.makedirs(DATASETS_BASE, exist_ok=True)


class AdaptiveDatasetManager:
    """
    Constructs balanced training datasets with replay buffers for independent YOLO and U-Net retraining.
    """

    CLASS_NAMES = [
        "fishing_net", "pipeline_or_cable", "shipwreck_fragment",
        "engine_debris", "riprap_debris", "metal_container", "tire", "plastic_debris"
    ]

    def __init__(self, versions_dir: str = DATASETS_BASE):
        self.versions_dir = versions_dir
        self.current_version = "v1.1"

    def create_versioned_dataset(
        self,
        new_version: str,
        human_corrections: List[Dict[str, Any]],
        hard_negatives: List[Dict[str, Any]],
        include_baseline_samples: int = 50
    ) -> Dict[str, Any]:
        """
        Synthesizes a new balanced dataset version blending baseline data, verified corrections, and hard negatives.
        """
        ver_dir = os.path.join(self.versions_dir, new_version)
        images_train_dir = os.path.join(ver_dir, "images", "train")
        images_val_dir = os.path.join(ver_dir, "images", "val")
        labels_train_dir = os.path.join(ver_dir, "labels", "train")
        labels_val_dir = os.path.join(ver_dir, "labels", "val")
        masks_train_dir = os.path.join(ver_dir, "masks", "train")

        for d in (images_train_dir, images_val_dir, labels_train_dir, labels_val_dir, masks_train_dir):
            os.makedirs(d, exist_ok=True)

        added_samples = 0
        hard_neg_count = 0

        # 1. Incorporate Hard Negatives (Empty label file = YOLO background hard negative)
        for idx, hn in enumerate(hard_negatives):
            crop_p = hn.get("crop_path")
            if crop_p and os.path.exists(crop_p):
                dest_img = os.path.join(images_train_dir, f"hard_neg_{idx:04d}.png")
                dest_lbl = os.path.join(labels_train_dir, f"hard_neg_{idx:04d}.txt")
                shutil.copy2(crop_p, dest_img)
                # Create empty label file for hard negative background
                with open(dest_lbl, "w") as f:
                    f.write("")
                hard_neg_count += 1
                added_samples += 1

        # 2. Incorporate Positive Human Corrections
        for idx, hc in enumerate(human_corrections):
            crop_p = hc.get("crop_path")
            cls_name = hc.get("correct_class", "fishing_net")
            if crop_p and os.path.exists(crop_p) and cls_name != "background":
                dest_img = os.path.join(images_train_dir, f"human_corr_{idx:04d}.png")
                dest_lbl = os.path.join(labels_train_dir, f"human_corr_{idx:04d}.txt")
                shutil.copy2(crop_p, dest_img)

                cls_id = self.CLASS_NAMES.index(cls_name) if cls_name in self.CLASS_NAMES else 0
                # Centered bounding box in normalized crop coordinates
                with open(dest_lbl, "w") as f:
                    f.write(f"{cls_id} 0.500000 0.500000 0.850000 0.850000\n")
                added_samples += 1

        # 3. Incorporate Baseline Replay Samples to prevent catastrophic forgetting
        if os.path.exists(BASE_YOLO_DATASET):
            base_train_img = os.path.join(BASE_YOLO_DATASET, "images", "train")
            base_train_lbl = os.path.join(BASE_YOLO_DATASET, "labels", "train")
            if os.path.exists(base_train_img):
                fnames = [f for f in os.listdir(base_train_img) if f.lower().endswith((".png", ".jpg", ".tif"))][:include_baseline_samples]
                for fn in fnames:
                    src_i = os.path.join(base_train_img, fn)
                    lbl_fn = os.path.splitext(fn)[0] + ".txt"
                    src_l = os.path.join(base_train_lbl, lbl_fn)

                    shutil.copy2(src_i, os.path.join(images_train_dir, fn))
                    if os.path.exists(src_l):
                        shutil.copy2(src_l, os.path.join(labels_train_dir, lbl_fn))
                    added_samples += 1

        # Copy validation split
        if os.path.exists(BASE_YOLO_DATASET):
            base_val_img = os.path.join(BASE_YOLO_DATASET, "images", "val")
            base_val_lbl = os.path.join(BASE_YOLO_DATASET, "labels", "val")
            if os.path.exists(base_val_img):
                for fn in os.listdir(base_val_img)[:20]:
                    shutil.copy2(os.path.join(base_val_img, fn), os.path.join(images_val_dir, fn))
                    lbl_fn = os.path.splitext(fn)[0] + ".txt"
                    if os.path.exists(os.path.join(base_val_lbl, lbl_fn)):
                        shutil.copy2(os.path.join(base_val_lbl, lbl_fn), os.path.join(labels_val_dir, lbl_fn))

        # 4. Generate YOLO data.yaml
        data_yaml_path = os.path.join(ver_dir, "data.yaml")
        yaml_content = {
            "path": ver_dir,
            "train": "images/train",
            "val": "images/val",
            "names": {i: name for i, name in enumerate(self.CLASS_NAMES)}
        }
        with open(data_yaml_path, "w") as f:
            yaml.dump(yaml_content, f, sort_keys=False)

        self.current_version = new_version
        return {
            "version": new_version,
            "dataset_path": ver_dir,
            "data_yaml": data_yaml_path,
            "total_samples": added_samples,
            "hard_negatives": hard_neg_count,
            "created_at": datetime.utcnow().isoformat()
        }

    def get_dataset_stats(self) -> Dict[str, Any]:
        """Returns statistics for active dataset versions and accumulated feedback."""
        versions = [d for d in os.listdir(self.versions_dir) if os.path.isdir(os.path.join(self.versions_dir, d))]
        return {
            "active_version": self.current_version,
            "available_versions": sorted(versions),
            "classes": self.CLASS_NAMES,
            "base_dataset_available": os.path.exists(BASE_YOLO_DATASET)
        }
