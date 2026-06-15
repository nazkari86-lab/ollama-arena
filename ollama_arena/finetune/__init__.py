"""
Closed-loop fine-tuning — turn arena failures into training data,
then fine-tune weak models with Unsloth and re-test.

Pipeline:
  1. analyze_weaknesses(db)   — find weak (model, category) pairs from match_log
  2. build_dataset(weak)      — collect failed task instructions + reference solutions
  3. unsloth_train(dataset)   — LoRA fine-tune via Unsloth (requires CUDA)
  4. push_to_ollama(adapter)  — package adapter as Ollama Modelfile

Each step is optional and standalone.
"""
from .analyzer  import analyze_weaknesses, weakness_report
from .generator import build_training_dataset, save_jsonl
from .unsloth_runner import unsloth_train, UnslothConfig
from .ollama_export import build_modelfile, install_to_ollama

__all__ = [
    "analyze_weaknesses", "weakness_report",
    "build_training_dataset", "save_jsonl",
    "unsloth_train", "UnslothConfig",
    "build_modelfile", "install_to_ollama",
]
