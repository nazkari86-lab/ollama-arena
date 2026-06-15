"""
ollama-arena — Local LLM ELO Arena.

Public API:

    from ollama_arena import Arena, EloStore
    from ollama_arena.backends import OllamaBackend, OpenAICompatBackend
    from ollama_arena.sandboxes import run_in_language
    from ollama_arena.datasets import load_dataset
    from ollama_arena.visualize import elo_timeline_html, export_dashboard
    from ollama_arena.finetune import analyze_weaknesses, unsloth_train
"""
__version__ = "2.0.0"
__author__  = "nazkari86-lab"

from .arena import Arena, OllamaClient, MatchResult
from .backends import Backend, OllamaBackend, OpenAICompatBackend, GenResult
from .elo import EloStore, update_elo
from .performance import PerfTracker
from .tasks import get_tasks, task_stats, list_categories, list_languages
from .evaluator import evaluate

__all__ = [
    "__version__",
    "Arena", "OllamaClient", "MatchResult",
    "Backend", "OllamaBackend", "OpenAICompatBackend", "GenResult",
    "EloStore", "update_elo", "PerfTracker",
    "get_tasks", "task_stats", "list_categories", "list_languages",
    "evaluate",
]
