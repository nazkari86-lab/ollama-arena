"""Continuous Auto-Finetuning system for ollama-arena.

This module provides automated, continuous fine-tuning capabilities that:
1. Extract DPO pairs from arena match results (winner vs loser responses)
2. Automatically trigger fine-tuning when performance thresholds are met
3. Generate adversarial datasets to target weak areas
4. Orchestrate GPU resources and fine-tuning jobs

The system integrates with the existing finetune module but adds automation
and orchestration capabilities.
"""

from .dpo_pipeline import (
    DPOPipeline,
    extract_dpo_pairs,
    collect_preference_dataset,
    format_dpo_dataset,
    validate_dpo_dataset,
    DatasetVersion,
    DatasetStorage,
)
from .unsloth_integration import (
    AutoUnslothIntegrator,
    FinetuneTrigger,
    LoRAConfig,
    AutoFinetuneResult,
    register_arena_model,
)
from .adversarial_gen import (
    AdversarialGenerator,
    TaskDifficultyAnalyzer,
    WeaknessTarget,
    generate_harder_tasks,
    calibrate_difficulty,
}
from .orchestrator import (
    FinetuningOrchestrator,
    FinetuningJob,
    JobQueue,
    GPUAllocator,
    FinetuningMonitor,
)

__all__ = [
    # DPO Pipeline
    "DPOPipeline",
    "extract_dpo_pairs",
    "collect_preference_dataset",
    "format_dpo_dataset",
    "validate_dpo_dataset",
    "DatasetVersion",
    "DatasetStorage",
    # Auto-Unsloth Integration
    "AutoUnslothIntegrator",
    "FinetuneTrigger",
    "LoRAConfig",
    "AutoFinetuneResult",
    "register_arena_model",
    # Adversarial Generation
    "AdversarialGenerator",
    "TaskDifficultyAnalyzer",
    "WeaknessTarget",
    "generate_harder_tasks",
    "calibrate_difficulty",
    # Orchestration
    "FinetuningOrchestrator",
    "FinetuningJob",
    "JobQueue",
    "GPUAllocator",
    "FinetuningMonitor",
]
