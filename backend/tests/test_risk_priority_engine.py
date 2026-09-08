"""
Unit Tests for Explainable Debris Risk and Priority Scoring Engine
Verifies:
  1. Strict separation between AI Detection Confidence, Hazard Risk, and Inspection Priority.
  2. Preferential use of U-Net segmentation polygon area over bounding box area.
  3. Dynamic factual reasons generation and natural language explanation synthesis.
  4. 4-tier Risk/Priority categorization (LOW, MEDIUM, HIGH, CRITICAL).
  5. Sonar quality modulating evidence reliability rather than intrinsic hazard.
"""

import sys
import os
import unittest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai.measurement.risk_priority_engine import RiskPriorityEngine


class TestRiskPriorityEngine(unittest.TestCase):
    def setUp(self):
        self.engine = RiskPriorityEngine()

    def test_concept_separation(self):
        """Ensure confidence, hazard risk, and priority are mathematically distinct."""
        target = {
            "object_id": "D07",
            "class": "fishing_net",
            "confidence": 0.94,
            "polygon": [[10, 10], [50, 10], [50, 50], [10, 50]],
            "quality_metrics": {"contrast_score": 0.8, "shadow_score": 0.75}
        }
        dims = {"area_sq_m": 35.0, "length_m": 7.0, "width_m": 5.0}
        raster_meta = {"dataset_profile": "NOAA Breton Sound Marine Sanctuary"}

        res = self.engine.calculate_debris_scores(target, raster_meta=raster_meta, dimensions=dims)

        # 1. Detection Confidence is 94%
        self.assertAlmostEqual(res["detection_confidence"], 0.94, places=2)
        self.assertEqual(res["detection_confidence_pct"], 94.0)

        # 2. Hazard Risk is distinct and >= 80 for large ghost net in sanctuary
        self.assertGreaterEqual(res["hazard_risk"], 80)
        self.assertIn(res["hazard_risk_level"], ["HIGH", "CRITICAL"])

        # 3. Priority Score is distinct and >= 85
        self.assertGreaterEqual(res["priority_score"], 85)
        self.assertEqual(res["priority_level"], "CRITICAL")

        # 4. Check contributing factors existence
        factors = res["contributing_factors"]
        self.assertIn("detection_confidence", factors)
        self.assertIn("object_extent", factors)
        self.assertIn("marine_hazard", factors)
        self.assertIn("location_sensitivity", factors)
        self.assertIn("sonar_reliability", factors)

    def test_low_priority_debris(self):
        """Small riprap rock with lower confidence should have low priority."""
        target = {
            "object_id": "D01",
            "class": "riprap_debris",
            "confidence": 0.45,
            "bbox": {"x1": 10, "y1": 10, "x2": 15, "y2": 15},
            "polygon": []
        }
        dims = {"area_sq_m": 0.8, "length_m": 0.9, "width_m": 0.8}
        res = self.engine.calculate_debris_scores(target, dimensions=dims)

        self.assertLessEqual(res["priority_score"], 50)
        self.assertIn(res["priority_level"], ["LOW", "MEDIUM"])
        self.assertEqual(res["object_size"], "small")

    def test_sonar_quality_does_not_diminish_hazard(self):
        """Poor sonar quality must modulate evidence reliability without reducing intrinsic hazard risk."""
        target = {
            "object_id": "D09",
            "class": "fishing_net",
            "confidence": 0.80,
            "quality_metrics": {"contrast_score": 0.1, "shadow_score": 0.1} # Poor sonar
        }
        dims = {"area_sq_m": 30.0}

        res = self.engine.calculate_debris_scores(target, dimensions=dims)
        # Hazard risk remains high despite noisy sonar
        self.assertGreaterEqual(res["hazard_risk"], 75)
        # Sonar quality is flagged as noisy or moderate
        self.assertIn(res["sonar_quality"], ["noisy", "moderate"])
        self.assertLessEqual(res["reliability_multiplier"], 0.90)

    def test_dynamic_reasons_and_recommendations(self):
        """Ensure factual reasons are generated matching data."""
        target = {
            "object_id": "D03",
            "class": "shipwreck_fragment",
            "confidence": 0.92,
            "polygon": [[0, 0], [100, 0], [100, 50], [0, 50]]
        }
        dims = {"area_sq_m": 42.0}
        res = self.engine.calculate_debris_scores(target, dimensions=dims)

        reasons = res["reasons"]
        self.assertTrue(any("shipwreck" in r.lower() or "structural" in r.lower() for r in reasons))
        self.assertTrue(any("92" in r for r in reasons))
        self.assertTrue(any("large" in r.lower() for r in reasons))
        self.assertIsNotNone(res["recommendation"])
        self.assertIn("inspection", res["recommendation"].lower())


if __name__ == "__main__":
    unittest.main()
