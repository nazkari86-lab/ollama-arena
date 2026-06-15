"""
Real benchmark datasets pulled from HuggingFace Hub.

Supports:
  • HumanEval        (openai_humaneval)              — Python code generation
  • MBPP             (mbpp)                          — Python code generation
  • MBPP+            (evalplus/mbppplus)             — extended MBPP
  • GSM8K            (gsm8k)                         — grade-school math
  • MMLU             (cais/mmlu)                     — 57-subject knowledge
  • BBH              (lukaemon/bbh)                  — Big-Bench Hard
  • MultiPL-E        (nuprl/MultiPL-E)               — code gen in 22 languages
  • TruthfulQA       (truthful_qa)                   — factual honesty
  • HellaSwag        (hellaswag)                     — common-sense reasoning
  • ARC              (ai2_arc)                       — science questions

Auto-cached under ~/.cache/ollama_arena/datasets/
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
