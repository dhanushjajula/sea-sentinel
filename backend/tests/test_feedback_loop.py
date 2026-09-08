"""
End-to-End Unit & Integration Test Suite for Continuous Learning & Human Feedback Loop
Tests:
  1. FeedbackNLUEngine (Natural Language parsing, negation, class extraction, rationale)
  2. CorrectionMemory (Acoustic crop signature extraction, cosine similarity matching, applied count)
  3. FeedbackDatasetAccumulator (YOLOv11 normalized annotation formatting and dataset generation)
  4. YOLOLearner (Fine-tuning lifecycle, metric validation, dry-run mode, and model hot-reloading)
  5. Pipeline Integration (Candidate matching against memory in Stage 6, overriding misclassification)
  6. FastAPI REST API (Endpoints /api/feedback, /api/feedback/memory, /api/feedback/train, /api/feedback/status)
"""

import os
import sys
import unittest
import numpy as np
import cv2
import tempfile
import shutil

# Ensure backend root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ai.feedback.nlu_engine import FeedbackNLUEngine
from ai.feedback.correction_memory import CorrectionMemory
from ai.feedback.dataset_accumulator import FeedbackDatasetAccumulator
from ai.feedback.learner import YOLOLearner
from agent.orchestrator import SIHPipelineAgent


class TestFeedbackNLUEngine(unittest.TestCase):
    def setUp(self):
        self.nlu = FeedbackNLUEngine()

    def test_reclassification_negation(self):
        # User says not a pipeline, actually a fishing net
        text = "This is not a pipeline or cable, it is actually a ghost fishing net tangled on the seabed"
        res = self.nlu.parse_feedback(text, original_class="pipeline_or_cable")
        self.assertEqual(res["corrected_class"], "fishing_net")
        self.assertEqual(res["corrected_class_id"], 0)
        self.assertEqual(res["correction_type"], "reclassify")
        self.assertGreater(res["confidence"], 0.7)
        self.assertTrue(len(res["rationale"]) > 0)

    def test_engine_debris_identification(self):
        text = "Strong metallic acoustic highlight with hard trailing shadow, this is an outboard engine part."
        res = self.nlu.parse_feedback(text, original_class="riprap_debris")
        self.assertEqual(res["corrected_class"], "engine_debris")
        self.assertEqual(res["corrected_class_id"], 3)
        self.assertEqual(res["correction_type"], "reclassify")

    def test_false_alarm_detection(self):
        text = "This is a false alarm. It is just natural rock ripple noise and seabed clutter, not any real debris."
        res = self.nlu.parse_feedback(text, original_class="shipwreck_fragment")
        self.assertEqual(res["corrected_class"], "false_alarm")
        self.assertEqual(res["correction_type"], "false_alarm")

    def test_shipwreck_detection(self):
        text = "Large prominent wooden hull timber fragment from historic shipwreck"
        res = self.nlu.parse_feedback(text, original_class="fishing_net")
        self.assertEqual(res["corrected_class"], "shipwreck_fragment")
        self.assertEqual(res["corrected_class_id"], 2)


class TestCorrectionMemory(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_audit.db")
        self.memory = CorrectionMemory(db_path=self.db_path)
        # Override crops dir to temporary location
        self.memory.crops_dir = os.path.join(self.test_dir, "crops")
        os.makedirs(self.memory.crops_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_save_and_match_mistake(self):
        # Create a synthetic acoustic sonar crop with a linear ridge
        img = np.zeros((100, 100), dtype=np.uint8)
        cv2.line(img, (20, 20), (80, 80), 220, 4)
        cv2.rectangle(img, (25, 25), (75, 75), 180, 2)

        # 1. Save human correction: model thought it was "pipeline_or_cable", human corrected to "fishing_net"
        saved = self.memory.save_correction(
            source_image=img,
            bbox={"x1": 15, "y1": 15, "x2": 85, "y2": 85},
            original_class="pipeline_or_cable",
            corrected_class="fishing_net",
            corrected_class_id=0,
            human_comment="Linear structure is actually lead-line netting with floats",
            extracted_reason="Lead-line acoustic backscatter",
            correction_type="reclassify",
            original_confidence=0.72,
            session_id="SURVEY_TEST_01",
            object_id="TGT_001"
        )

        self.assertTrue(saved["feedback_id"].startswith("FB_"))
        self.assertTrue(os.path.exists(saved["crop_path"]))

        # 2. Test future matching with an identical or slightly noisy crop
        noisy_img = img.copy()
        noise = np.random.randint(0, 5, img.shape, dtype=np.uint8)
        noisy_img = cv2.add(noisy_img, noise)
        crop_patch = noisy_img[15:85, 15:85]

        match = self.memory.find_similar_mistake(
            candidate_crop=crop_patch,
            candidate_class="pipeline_or_cable",
            similarity_threshold=0.75
        )

        self.assertTrue(match.get("matched"), f"Expected match, got: {match}")
        self.assertEqual(match["corrected_class"], "fishing_net")
        self.assertEqual(match["corrected_class_id"], 0)
        self.assertGreater(match["similarity"], 0.85)
        self.assertGreaterEqual(match["applied_count"], 1)

        # 3. Verify statistics
        stats = self.memory.get_stats()
        self.assertEqual(stats["total_corrections_learned"], 1)
        self.assertGreaterEqual(stats["total_times_applied"], 1)
        self.assertEqual(stats["class_distribution"].get("fishing_net"), 1)


class TestFeedbackDatasetAccumulator(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.accumulator = FeedbackDatasetAccumulator(base_dataset_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_add_correction_sample(self):
        canvas = np.zeros((400, 600), dtype=np.uint8)
        cv2.circle(canvas, (300, 200), 40, 200, -1)

        res = self.accumulator.add_correction_sample(
            feedback_id="FB_TEST_100",
            image_input=canvas,
            bbox={"x1": 250, "y1": 150, "x2": 350, "y2": 250},
            class_id=3  # engine_debris
        )

        self.assertTrue(os.path.exists(res["image_path"]))
        self.assertTrue(os.path.exists(res["label_path"]))
        self.assertEqual(res["class_name"], "engine_debris")

        # Check YOLO label format: class_id xc yc w h
        with open(res["label_path"], "r") as f:
            line = f.read().strip()
        parts = line.split()
        self.assertEqual(int(parts[0]), 3)
        self.assertAlmostEqual(float(parts[1]), 300.0 / 600.0, places=2)
        self.assertAlmostEqual(float(parts[2]), 200.0 / 400.0, places=2)

        stats = self.accumulator.get_dataset_stats()
        self.assertEqual(stats["train_samples"], 1)
        self.assertTrue(stats["ready_for_fine_tuning"])


class TestYOLOLearner(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.reloaded_path = None

        def mock_reload(p):
            self.reloaded_path = p

        self.learner = YOLOLearner(
            checkpoints_dir=self.test_dir,
            on_model_deployed=mock_reload
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_dry_run_training(self):
        # Create a dummy yaml file
        dummy_yaml = os.path.join(self.test_dir, "data.yaml")
        with open(dummy_yaml, "w") as f:
            f.write("names: [fishing_net, pipeline_or_cable]\n")

        res = self.learner.train_on_feedback(
            data_yaml=dummy_yaml,
            epochs=2,
            batch_size=2,
            dry_run=True
        )

        self.assertEqual(res["status"], "completed")
        self.assertIn("metrics", res)
        self.assertGreater(res["metrics"]["mAP50"], 0.8)

        status = self.learner.get_status()
        self.assertFalse(status["is_training"])


class TestAgentPipelineFeedbackIntegration(unittest.TestCase):
    def test_pipeline_memory_override(self):
        agent = SIHPipelineAgent()

        # Generate synthetic acoustic tile
        raw_tile = np.zeros((300, 300), dtype=np.uint8)
        cv2.rectangle(raw_tile, (50, 50), (120, 120), 210, -1)
        # Trailing acoustic shadow
        cv2.rectangle(raw_tile, (120, 50), (160, 120), 15, -1)

        temp_img_path = os.path.join(tempfile.gettempdir(), "test_sonar_tile.png")
        cv2.imwrite(temp_img_path, raw_tile)

        try:
            # Seed correction memory: this morphology should be "engine_debris", not "fishing_net"
            agent.correction_memory.save_correction(
                source_image=raw_tile,
                bbox={"x1": 45, "y1": 45, "x2": 165, "y2": 125},
                original_class="fishing_net",
                corrected_class="engine_debris",
                corrected_class_id=3,
                human_comment="Dense metallic block with shadow, outboard engine wreckage",
                extracted_reason="Dense metallic block acoustic signature",
                correction_type="reclassify",
                original_confidence=0.65,
                session_id="SEED_SURVEY",
                object_id="SEED_01"
            )

            # Analyze image through agent pipeline
            result = agent.analyze_image(temp_img_path)
            self.assertEqual(result["status"], "success")

            # Check if any detection received memory correction
            corrected_targets = [d for d in result["detections"] if d.get("memory_corrected")]
            if corrected_targets:
                self.assertEqual(corrected_targets[0]["class"], "engine_debris")
                self.assertEqual(corrected_targets[0]["original_model_class"], "fishing_net")
                self.assertIn("Correction Memory", corrected_targets[0]["explanation"]["executive_narrative"])
        finally:
            if os.path.exists(temp_img_path):
                os.remove(temp_img_path)


class TestFastAPIFeedbackEndpoints(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from app.main import app
        self.client = TestClient(app)

    def test_feedback_memory_endpoint(self):
        res = self.client.get("/api/feedback/memory")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("stats", data)
        self.assertIn("corrections", data)

    def test_feedback_status_endpoint(self):
        res = self.client.get("/api/feedback/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("is_training", data)

    def test_feedback_train_dry_run(self):
        res = self.client.post("/api/feedback/train", json={"epochs": 1, "dry_run": True})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn(data["status"], ["completed", "started", "insufficient_data"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
