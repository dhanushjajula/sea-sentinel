"""
Sea Sentinel: Adaptive Learning & Error Prevention Package
Provides Review Intelligence, Error Memory, Active Learning, Unknown Object Lifecycle,
Anti-Forgetting Balanced Dataset Generation, Champion vs Challenger Evaluation,
and Historical Error Regression Testing.
"""

from .review_intelligence import ReviewIntelligenceEngine, StructuredErrorRecord
from .error_memory import ErrorMemoryEngine
from .active_learner import ActiveLearningEngine
from .unknown_objects import UnknownObjectManager
from .dataset_manager import AdaptiveDatasetManager
from .trainers import ModelRetrainingOrchestrator
from .evaluator import ChampionChallengerEvaluator
from .deployment_manager import AdaptiveDeploymentManager

__all__ = [
    "ReviewIntelligenceEngine",
    "StructuredErrorRecord",
    "ErrorMemoryEngine",
    "ActiveLearningEngine",
    "UnknownObjectManager",
    "AdaptiveDatasetManager",
    "ModelRetrainingOrchestrator",
    "ChampionChallengerEvaluator",
    "AdaptiveDeploymentManager"
]
