"""SFT pipeline driven by arena results.

The pipeline is intentionally split: each step can be replaced or
skipped (e.g. use your own dataset, your own trainer, your own quant).
"""
from .analyzer  import analyze_weaknesses, weakness_report, analyze_task_failures, task_failure_report
from .generator import build_training_dataset, build_dpo_dataset, save_jsonl
from .unsloth_runner import unsloth_train, UnslothConfig, macos_fallback_train
from .ollama_export import build_modelfile, install_to_ollama

__all__ = [
    "analyze_weaknesses", "weakness_report", "analyze_task_failures", "task_failure_report",
    "build_training_dataset", "build_dpo_dataset", "save_jsonl",
    "unsloth_train", "UnslothConfig", "macos_fallback_train",
    "build_modelfile", "install_to_ollama",
]
