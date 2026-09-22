import cv2
import os
import sys
import json

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from ai.detection.yolo_detector import YOLODetector
from ai.segmentation.unet_segmenter import UNetSegmenter

def main():
    yolo = YOLODetector()
    unet = UNetSegmenter()

    samples = [
        "datasets/samples/china_offshore_quanzhou_net.jpg",
        "datasets/samples/china_offshore_dongying_pipeline.jpg",
        "datasets/samples/china_offshore_dongying_engine.jpg",
        "datasets/samples/towfish_mission_case_b.png"
    ]

    for s in samples:
        if not os.path.exists(s):
            print(f"Missing {s}")
            continue
        img = cv2.imread(s)
        h, w = img.shape[:2]
        y_res = yolo.detect(img, conf_override=0.25)
        dets = y_res.get("detections", [])
        print(f"\n=== {s} ({w}x{h}) ===")
        print(f"Detections found: {len(dets)}")
        for d in dets:
            b = d["bbox"]
            cls_name = d["class"]
            conf = d["confidence"]
            print(f"  Class: {cls_name}, Conf: {conf:.3f}, Box: [{b['x1']}, {b['y1']}, {b['x2']}, {b['y2']}]")
            x1, y1, x2, y2 = int(b["x1"]), int(b["y1"]), int(b["x2"]), int(b["y2"])
            crop = img[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
            if crop.size > 0:
                seg = unet.segment_crop(crop, offset_xy=(x1, y1))
                poly = seg.get("polygon", [])
                area = seg.get("total_area_px", 0)
                mean_c = seg.get("mean_confidence", 0.0)
                print(f"    Mask Area: {area} px, Mean Conf: {mean_c:.3f}, Poly points: {len(poly)}")
                if len(poly) > 0:
                    print(f"    Poly sample: {poly[:3]} ...")

if __name__ == "__main__":
    main()
