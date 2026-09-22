"""
Sea Sentinel: Adaptive Learning & Error Prevention Package
Redirects to backend.review_intelligence module.
"""

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
