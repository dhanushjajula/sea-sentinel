"""
Feedback Dataset Accumulator
Converts human corrections into standardized YOLOv11 training samples:
  - Generates normalized bounding box annotations (`class_idx xc yc w h`)
  - Archives images and labels in `datasets/processed/yolo_dataset/feedback/`
  - Maintains `feedback_data.yaml` ready for periodic transfer-learning fine-tuning
"""

from typing import Dict, Any, List, Optional, Union
import os
import shutil
import yaml
import cv2
import numpy as np


class FeedbackDatasetAccumulator:
    """
    Accumulates human-verified sonar examples into YOLOv11 dataset format.
    """

    CLASS_NAMES = {
        0: "fishing_net",
        1: "pipeline_or_cable",
        2: "shipwreck_fragment",
        3: "engine_debris",
        4: "riprap_debris"
    }

    def __init__(self, base_dataset_dir: Optional[str] = None):
        if base_dataset_dir is None:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.feedback_dir = os.path.join(project_root, "datasets", "processed", "yolo_dataset", "feedback")
        else:
            self.feedback_dir = base_dataset_dir

        self.images_train = os.path.join(self.feedback_dir, "images", "train")
        self.labels_train = os.path.join(self.feedback_dir, "labels", "train")
        self.images_val = os.path.join(self.feedback_dir, "images", "val")
        self.labels_val = os.path.join(self.feedback_dir, "labels", "val")

        for d in [self.images_train, self.labels_train, self.images_val, self.labels_val]:
            os.makedirs(d, exist_ok=True)

        self.data_yaml_path = os.path.join(self.feedback_dir, "feedback_data.yaml")
        self._ensure_yaml_config()

    def _ensure_yaml_config(self):
        """Creates feedback_data.yaml if not present."""
        data_cfg = {
            "path": os.path.abspath(self.feedback_dir),
            "train": "images/train",
            "val": "images/val",
            "names": self.CLASS_NAMES
        }
        with open(self.data_yaml_path, "w") as f:
            yaml.dump(data_cfg, f, default_flow_style=False)

    def add_correction_sample(
        self,
        feedback_id: str,
        image_input: Union[str, np.ndarray],
        bbox: Dict[str, Any],
        class_id: int,
        is_val: bool = False
    ) -> Dict[str, Any]:
        """
        Ingests a corrected image region and generates normalized YOLO label.
        bbox format: {'x1': float, 'y1': float, 'x2': float, 'y2': float}
        """
        # Load image matrix
        if isinstance(image_input, str):
            if not os.path.exists(image_input):
                raise FileNotFoundError(f"Image not found: {image_input}")
            img_mat = cv2.imread(image_input, cv2.IMREAD_UNCHANGED)
        else:
            img_mat = image_input

        if img_mat is None or img_mat.size == 0:
            raise ValueError("Invalid image input for dataset accumulation.")

        h_img, w_img = img_mat.shape[:2]

        x1 = max(0.0, min(float(w_img - 1), float(bbox.get("x1", 0))))
        y1 = max(0.0, min(float(h_img - 1), float(bbox.get("y1", 0))))
        x2 = max(x1 + 4.0, min(float(w_img), float(bbox.get("x2", w_img))))
        y2 = max(y1 + 4.0, min(float(h_img), float(bbox.get("y2", h_img))))

        # Compute normalized YOLO coordinates (xc, yc, w, h in [0, 1])
        box_w = x2 - x1
        box_h = y2 - y1
        xc = (x1 + box_w / 2.0) / float(w_img)
        yc = (y1 + box_h / 2.0) / float(h_img)
        nw = box_w / float(w_img)
        nh = box_h / float(h_img)

        # Clamp safely
        xc = max(0.0, min(1.0, xc))
        yc = max(0.0, min(1.0, yc))
        nw = max(0.001, min(1.0, nw))
        nh = max(0.001, min(1.0, nh))

        target_img_dir = self.images_val if is_val else self.images_train
        target_lbl_dir = self.labels_val if is_val else self.labels_train

        img_filename = f"{feedback_id}.png"
        lbl_filename = f"{feedback_id}.txt"

        save_img_path = os.path.join(target_img_dir, img_filename)
        save_lbl_path = os.path.join(target_lbl_dir, lbl_filename)

        # Save image (convert uint8 if necessary)
        save_mat = img_mat
        if save_mat.dtype != np.uint8:
            save_mat = cv2.normalize(save_mat, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        cv2.imwrite(save_img_path, save_mat)

        # Write YOLO label: class_idx xc yc w h
        label_line = f"{int(class_id)} {xc:.6f} {yc:.6f} {nw:.6f} {nh:.6f}\n"
        with open(save_lbl_path, "w") as lf:
            lf.write(label_line)

        return {
            "feedback_id": feedback_id,
            "image_path": save_img_path,
            "label_path": save_lbl_path,
            "class_id": class_id,
            "class_name": self.CLASS_NAMES.get(class_id, "unknown"),
            "yolo_bbox": [xc, yc, nw, nh],
            "split": "val" if is_val else "train"
        }

    def get_dataset_stats(self) -> Dict[str, Any]:
        """Returns count of accumulated training and validation examples."""
        train_count = len([f for f in os.listdir(self.images_train) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
        val_count = len([f for f in os.listdir(self.images_val) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
        return {
            "feedback_dataset_path": self.feedback_dir,
            "yaml_config": self.data_yaml_path,
            "train_samples": train_count,
            "val_samples": val_count,
            "total_samples": train_count + val_count,
            "ready_for_fine_tuning": train_count > 0
        }
