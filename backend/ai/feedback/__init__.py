"""
Human-in-the-Loop (HITL) Feedback & Continuous Learning Module
Provides:
  - NLUEngine: Natural language feedback understanding and class extraction
  - CorrectionMemory: Persistent SQLite memory and acoustic similarity matching for future detections
  - FeedbackDatasetAccumulator: Converts human corrections into YOLO format training samples
  - YOLOLearner: Periodic transfer-learning fine-tuning and model hot-reloading
"""

from .nlu_engine import FeedbackNLUEngine
from .correction_memory import CorrectionMemory
from .dataset_accumulator import FeedbackDatasetAccumulator
from .learner import YOLOLearner

__all__ = [
    "FeedbackNLUEngine",
    "CorrectionMemory",
    "FeedbackDatasetAccumulator",
    "YOLOLearner"
]
