"""
Sea Sentinel: Adaptive Learning & Error Prevention Package
Redirects to backend.review_intelligence module.
"""

<<<<<<< HEAD
try:
    from backend.review_intelligence import (
        ReviewIntelligenceEngine,
        StructuredErrorRecord,
        ErrorMemoryEngine,
        ActiveLearningEngine,
        UnknownObjectManager,
        AdaptiveDatasetManager,
        ModelRetrainingOrchestrator,
        ChampionChallengerEvaluator,
        AdaptiveDeploymentManager
    )
except ImportError:
    from review_intelligence import (
        ReviewIntelligenceEngine,
        StructuredErrorRecord,
        ErrorMemoryEngine,
        ActiveLearningEngine,
        UnknownObjectManager,
        AdaptiveDatasetManager,
        ModelRetrainingOrchestrator,
        ChampionChallengerEvaluator,
        AdaptiveDeploymentManager
    )
=======
from backend.review_intelligence import (
    ReviewIntelligenceEngine,
    StructuredErrorRecord,
    ErrorMemoryEngine,
    ActiveLearningEngine,
    UnknownObjectManager,
    AdaptiveDatasetManager,
    ModelRetrainingOrchestrator,
    ChampionChallengerEvaluator,
    AdaptiveDeploymentManager
)
>>>>>>> 449ab6fff1827af49bd4a885932dc0cd8729161f

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
