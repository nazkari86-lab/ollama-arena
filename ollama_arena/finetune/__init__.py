"""
Closed-loop fine-tuning pipeline.

    analyze_weaknesses          Find (model, category) pairs with win_rate < 0.5
    build_training_dataset      Distill solutions from a teacher model
    unsloth_train               LoRA fine-tune via Unsloth, optional GGUF export
    build_modelfile             Wrap a GGUF as an Ollama Modelfile
    install_to_ollama           ollama create the new model

Each step is independent and can be used on its own.
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
