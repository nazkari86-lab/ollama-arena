"""SFT / DPO pipeline driven by arena results.

Simple API (legacy, always available):
    from ollama_arena.finetune import analyze_weaknesses, build_dpo_dataset, ...

Full orchestration (requires GPU + unsloth):
    from ollama_arena.finetune import FinetuningOrchestrator, DPOPipeline, ...
"""
from .analyzer  import analyze_weaknesses, weakness_report, analyze_task_failures, task_failure_report
from .generator import build_training_dataset, build_dpo_dataset, save_jsonl
from .unsloth_runner import unsloth_train, UnslothConfig, macos_fallback_train
from .ollama_export import build_modelfile, install_to_ollama

# Re-export the comprehensive orchestration layer from the finetuning package.
# These are optional; import errors surface only when callers use them.
try:
    from ..finetuning import (
        DPOPipeline, extract_dpo_pairs, collect_preference_dataset,
        format_dpo_dataset, validate_dpo_dataset, DatasetVersion, DatasetStorage,
        AutoUnslothIntegrator, FinetuneTrigger, LoRAConfig, AutoFinetuneResult,
        register_arena_model,
        AdversarialGenerator, TaskDifficultyAnalyzer, WeaknessTarget,
        generate_harder_tasks, calibrate_difficulty,
        FinetuningOrchestrator, FinetuningJob, JobQueue, GPUAllocator,
        FinetuningMonitor,
    )
    _HAS_ORCHESTRATION = True
except Exception:  # unsloth/GPU deps missing
    _HAS_ORCHESTRATION = False

__all__ = [
    # Core (always available)
    "analyze_weaknesses", "weakness_report", "analyze_task_failures", "task_failure_report",
    "build_training_dataset", "build_dpo_dataset", "save_jsonl",
    "unsloth_train", "UnslothConfig", "macos_fallback_train",
    "build_modelfile", "install_to_ollama",
    # Orchestration (when finetuning deps are present)
    "DPOPipeline", "extract_dpo_pairs", "collect_preference_dataset",
    "format_dpo_dataset", "validate_dpo_dataset", "DatasetVersion", "DatasetStorage",
    "AutoUnslothIntegrator", "FinetuneTrigger", "LoRAConfig", "AutoFinetuneResult",
    "register_arena_model",
    "AdversarialGenerator", "TaskDifficultyAnalyzer", "WeaknessTarget",
    "generate_harder_tasks", "calibrate_difficulty",
    "FinetuningOrchestrator", "FinetuningJob", "JobQueue", "GPUAllocator",
    "FinetuningMonitor",
]
