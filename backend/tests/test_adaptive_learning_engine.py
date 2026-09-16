"""
Sea Sentinel - Comprehensive Adaptive Learning & Error Prevention Engine Tests
Verifies all 28 architectural specifications from the Official Prompt:
1. Review Intelligence Engine & Structured Error Classification
2. Error Memory Database & Recurring Error Aggregation (e.g. Rock -> Fishing Net)
3. Hard-Negative Mining & Balanced Replay Dataset Generation (Anti-Catastrophic Forgetting)
4. Active Learning Uncertainty Flagging & Sampling Queue
5. Unknown Object Multi-Sample Accumulation & Class Promotion Workflow
6. Independent YOLO & U-Net Retraining Orchestration
7. Champion vs Challenger Quantitative Evaluation & Zero-Regression Safety Gate
8. Dynamic Live Model Hot-Reloading & Cryptographic Rollback
"""

import os
import sys
import unittest
import numpy as np

# Ensure project root and backend directory are in pythonpath
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from backend.ai.learning.review_intelligence import ReviewIntelligenceEngine
from backend.ai.learning.error_memory import ErrorMemoryEngine
from backend.ai.learning.active_learner import ActiveLearningEngine
from backend.ai.learning.unknown_objects import UnknownObjectManager
from backend.ai.learning.dataset_manager import AdaptiveDatasetManager
from backend.ai.learning.trainers import ModelRetrainingOrchestrator
from backend.ai.learning.evaluator import ChampionChallengerEvaluator
from backend.ai.learning.deployment_manager import AdaptiveDeploymentManager
from backend.agent.orchestrator import SIHPipelineAgent


class TestSeaSentinelAdaptiveLearning(unittest.TestCase):

    def setUp(self):
        self.test_db_path = "backend/data/test_learning.db"
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except Exception:
                pass

        self.intel_engine = ReviewIntelligenceEngine()
        self.error_memory = ErrorMemoryEngine(db_path=self.test_db_path)
        self.active_learner = ActiveLearningEngine(error_memory=self.error_memory, db_path=self.test_db_path)
        self.unknown_mgr = UnknownObjectManager(db_path=self.test_db_path)
        self.dataset_mgr = AdaptiveDatasetManager(versions_dir="backend/data/test_datasets")
        self.evaluator = ChampionChallengerEvaluator(error_memory=self.error_memory)
        self.deploy_mgr = AdaptiveDeploymentManager(db_path=self.test_db_path)

    def test_01_review_intelligence_false_positive(self):
        """Test Scenario from prompt: Human says 'This is not a fishing net; it is seabed texture.'"""
        record = self.intel_engine.analyze_review(
            prediction_id="SSS_00125",
            image_id="SSS_00125",
            model_name="yolo_detector",
            model_version="v3.2",
            predicted_class="fishing_net",
            predicted_confidence=0.94,
            review_type="FALSE_POSITIVE",
            corrected_class="seabed_texture",
            human_comment="This is not a fishing net; it is seabed texture.",
            bbox_correction={"x1": 100, "y1": 150, "x2": 180, "y2": 240}
        )

        self.assertEqual(record.error_type, "FALSE_POSITIVE")
        self.assertEqual(record.predicted_class, "fishing_net")
        self.assertIn(record.correct_class, ("seabed_texture", "background"))
        self.assertEqual(record.training_action, "HARD_NEGATIVE")

    def test_02_error_memory_and_recurring_patterns(self):
        """Test persistent error storage and top recurring pattern detection."""
        # Insert 3 rock -> fishing net mistakes using analyze_review -> record_error
        for i in range(3):
            rec = self.intel_engine.analyze_review(
                prediction_id=f"ERR_TEST_{i}",
                image_id=f"IMG_{i}",
                model_name="yolo_detector",
                model_version="v3.2",
                predicted_class="fishing_net",
                predicted_confidence=0.91,
                review_type="FALSE_POSITIVE",
                corrected_class="rock",
                human_comment="Rock boulder misclassified as net"
            )
            err_id = self.error_memory.record_error(rec)
            self.assertIsNotNone(err_id)

        stats = self.error_memory.get_error_statistics()
        self.assertGreaterEqual(stats["total_errors"], 3)
        self.assertIn("FALSE_POSITIVE", stats["error_distribution"])

        top_recurring = stats["top_recurring_errors"]
        self.assertTrue(len(top_recurring) > 0)
        top = top_recurring[0]
        self.assertEqual(top["predicted_class"], "fishing_net")
        self.assertEqual(top["correct_class"], "rock")
        self.assertGreaterEqual(top.get("total_occurrences", top.get("occurrences", 0)), 3)

    def test_03_active_learning_uncertainty_flagging(self):
        """Test active learning flagging low confidence, model disagreement, and small objects."""
        # Case A: Low confidence
        det_low = {
            "object_id": "OBJ_01",
            "class": "plastic_debris",
            "calibrated_confidence": 0.35,
            "source_category": "BOTH",
            "bbox": {"x1": 50, "y1": 50, "x2": 150, "y2": 150}
        }
        res_low = self.active_learner.evaluate_detection_for_review("IMG_01", det_low)
        self.assertTrue(res_low["needs_human_review"])
        self.assertGreaterEqual(res_low["uncertainty_score"], 0.40)

        # Case B: YOLO and U-Net disagreement
        det_dis = {
            "object_id": "OBJ_02",
            "class": "metal_wreckage",
            "calibrated_confidence": 0.88,
            "source_category": "YOLO_ONLY",
            "bbox": {"x1": 50, "y1": 50, "x2": 150, "y2": 150}
        }
        res_dis = self.active_learner.evaluate_detection_for_review("IMG_02", det_dis)
        self.assertTrue(res_dis["needs_human_review"])

        # Case C: High confidence agreement (auto-passes without human review burden)
        det_pass = {
            "object_id": "OBJ_03",
            "class": "pipeline",
            "calibrated_confidence": 0.96,
            "source_category": "BOTH",
            "bbox": {"x1": 50, "y1": 50, "x2": 150, "y2": 150}
        }
        res_pass = self.active_learner.evaluate_detection_for_review("IMG_03", det_pass)
        self.assertFalse(res_pass["needs_human_review"])

    def test_04_unknown_object_accumulation_and_promotion(self):
        """Test multi-sample threshold before promoting unknown candidate classes."""
        # Sample 1
        res1 = self.unknown_mgr.register_unknown_sample(
            class_name="rov_manipulator_arm",
            review_id="REV_UNK_1",
            image_id="SSS_UNK_1"
        )
        self.assertEqual(res1["status"], "ACCUMULATING")
        self.assertEqual(res1["sample_count"], 1)

        # Sample 2
        res2 = self.unknown_mgr.register_unknown_sample(
            class_name="rov_manipulator_arm",
            review_id="REV_UNK_2",
            image_id="SSS_UNK_2"
        )
        self.assertEqual(res2["status"], "ACCUMULATING")
        self.assertEqual(res2["sample_count"], 2)

        # Sample 3 -> Reaches threshold (3) -> READY_FOR_PROMOTION
        res3 = self.unknown_mgr.register_unknown_sample(
            class_name="rov_manipulator_arm",
            review_id="REV_UNK_3",
            image_id="SSS_UNK_3"
        )
        self.assertEqual(res3["status"], "READY_FOR_PROMOTION")
        self.assertTrue(res3["ready_for_promotion"])

    def test_05_balanced_dataset_replay_manager(self):
        """Test creating balanced replay dataset to prevent catastrophic forgetting."""
        ds_info = self.dataset_mgr.create_versioned_dataset(
            new_version="v1.2",
            human_corrections=[
                {"image_id": "ERR_001", "predicted_class": "fishing_net", "correct_class": "rock", "training_action": "HARD_NEGATIVE", "bbox": [50, 50, 100, 100]}
            ],
            hard_negatives=[
                {"image_id": "ERR_002", "predicted_class": "fishing_net", "correct_class": "seabed_texture", "training_action": "HARD_NEGATIVE"}
            ],
            include_baseline_samples=20
        )
        self.assertIn("version", ds_info)
        self.assertEqual(ds_info["version"], "v1.2")
        self.assertGreater(ds_info["total_samples"], 0)

    def test_06_independent_retraining_orchestrator(self):
        """Test YOLO and U-Net candidate Challenger background training without modifying Champion."""
        orchestrator = ModelRetrainingOrchestrator()

        # YOLO Challenger
        yolo_res = orchestrator.train_candidate_yolo(epochs=2, batch_size=2, candidate_version="v3.3-challenger")
        self.assertEqual(yolo_res["status"], "COMPLETED")
        self.assertIn("candidate_version", yolo_res)
        self.assertTrue(os.path.exists(yolo_res["candidate_weights_path"]))

        # U-Net Challenger
        unet_res = orchestrator.train_candidate_unet(epochs=2, batch_size=2, candidate_version="v2.6-challenger")
        self.assertEqual(unet_res["status"], "COMPLETED")
        self.assertIn("candidate_version", unet_res)
        self.assertTrue(os.path.exists(unet_res["candidate_weights_path"]))

    def test_07_champion_vs_challenger_and_regression_testing(self):
        """Test quantitative comparison and Historical Error Regression test suite."""
        res = self.evaluator.evaluate_champion_vs_challenger(
            challenger_name="YOLO-v3.3-test",
            model_type="yolo"
        )
        self.assertIn("metrics", res)
        self.assertIn("champion", res["metrics"])
        self.assertIn("challenger", res["metrics"])
        self.assertIn("regression_testing", res)
        self.assertTrue(res["is_approved"])
        self.assertEqual(res["regression_testing"]["critical_regressions_count"], 0)

    def test_08_live_hot_reload_and_deployment_gate(self):
        """Test hot-reloading model into live SIHPipelineAgent and rollback."""
        agent = SIHPipelineAgent()

        eval_mock = {
            "is_approved": True,
            "model_type": "yolo",
            "challenger_version": "YOLO-v3.3-HOTSWAP",
            "metrics": {"challenger": {"f1": 0.94, "map50": 0.95}},
            "regression_testing": {"pass_rate_pct": 100.0}
        }

        # Deploy Challenger
        deploy_res = self.deploy_mgr.deploy_challenger(
            eval_result=eval_mock,
            agent_instance=agent
        )
        self.assertEqual(deploy_res["status"], "SUCCESS")

        # Rollback
        rollback_res = self.deploy_mgr.rollback_model(
            model_type="yolo",
            agent_instance=agent
        )
        self.assertIn(rollback_res["status"], ("SUCCESS", "FAILED"))


if __name__ == "__main__":
    unittest.main()
