"""
HuggingFace Hub dataset loaders.

Built-in registry:
    humaneval, mbpp, mbpp_plus, gsm8k, mmlu, bbh,
    multipl_e, truthfulqa, hellaswag, arc

Each loader normalizes HF rows into the arena task schema. Downloaded
records are cached under ~/.cache/ollama_arena/datasets/ unless overridden
via the OLLAMA_ARENA_CACHE environment variable.
"""
from .loader import (
    load_dataset,
    available_datasets,
    cached_datasets,
    refresh_dataset,
    DatasetInfo,
)

__all__ = [
    "load_dataset", "available_datasets", "cached_datasets",
    "refresh_dataset", "DatasetInfo",
]
