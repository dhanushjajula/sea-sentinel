# Sea Sentinel — Review Intelligence & Adaptive Learning Engine

## Overview
The `review_intelligence` module provides the core Human-in-the-Loop (HITL) error analysis, persistent memory, active learning, dataset management, and regression testing engines for the Sea Sentinel marine sonar analysis system.

## Module Architecture

```text
backend/review_intelligence/
├── __init__.py                # Package exports
├── review_intelligence.py     # ReviewIntelligenceEngine (structured parsing & NLP taxonomy)
├── error_memory.py            # ErrorMemoryEngine (SQLite acoustic error storage & similarity)
├── active_learner.py          # ActiveLearningEngine (uncertainty & disagreement scoring)
├── unknown_objects.py         # UnknownObjectManager (novel class discovery & gating)
├── dataset_manager.py         # AdaptiveDatasetManager (anti-catastrophic forgetting replay)
├── trainers.py                # ModelRetrainingOrchestrator (YOLO & Attention U-Net background fine-tuning)
├── evaluator.py               # ChampionChallengerEvaluator (Zero-Regression test gate)
└── deployment_manager.py      # AdaptiveDeploymentManager (hot-reload & cryptographic rollback)
```

## Key Capabilities
- **Review Parsing**: Converts natural language human corrections into explicit machine-readable training actions (`HARD_NEGATIVE`, `RECLASSIFICATION`, `NEW_CLASS_CANDIDATE`).
- **Acoustic Error Memory**: Cosine similarity matching across 32-dim acoustic descriptors.
- **Novel Class Ontology Gating**: Requires $\ge 3$ human-confirmed instances before class promotion.
- **Balanced Replay Datasets**: 60% historical replay + 40% new corrections.
- **Zero-Regression Gate**: 100% pass on historical failure cases required for Challenger deployment.
- **Zero-Downtime Hot Reload**: Direct live model swapping in `SIHPipelineAgent`.
