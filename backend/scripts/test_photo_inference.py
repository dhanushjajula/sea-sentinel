"""
Test script to verify photo & sonar inference through the pipeline.
"""
import os
import json
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8000"

def test_photo_analysis():
    # Test on existing sample image
    sample_path = os.path.abspath("backend/datasets/samples/dongying_EP_001.png")
    if not os.path.exists(sample_path):
        sample_path = os.path.abspath("backend/datasets/samples/noaa_h11584_gulf_sample.tif")
    
    print(f"Testing analysis with image: {sample_path}")
    payload = {
        "image_path": sample_path,
        "mode": "balanced"
    }

    req = urllib.request.Request(
        f"{BASE_URL}/api/analyze",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"[SUCCESS] Status: {data.get('status')}")
            print(f"Analysis ID: {data.get('analysis_id')}")
            print(f"Total Detections: {len(data.get('detections', []))}")
            for idx, d in enumerate(data.get("detections", [])[:4]):
                print(f"  #{idx+1} {d.get('object_id')} | {d.get('class')} | Conf: {d.get('calibrated_confidence')} | Sources: {d.get('sources')}")
            return data
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8")
        print(f"[FAIL] HTTP {e.code}: {err}")
        return None

if __name__ == "__main__":
    test_photo_analysis()
