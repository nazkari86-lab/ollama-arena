"""Pair-wise evaluation arena for local LLMs."""
__version__ = "2.1.1"

from .arena import Arena, OllamaClient, MatchResult
from .backends import Backend, OllamaBackend, OpenAICompatBackend, GenResult
from .elo import EloStore, update_elo
from .performance import PerfTracker
from .tasks import get_tasks, task_stats, list_categories, list_languages
from .evaluator import evaluate
from .judge import LLMJudge, JudgeResult

__all__ = [
    "__version__",
    "Arena", "OllamaClient", "MatchResult",
    "Backend", "OllamaBackend", "OpenAICompatBackend", "GenResult",
    "EloStore", "update_elo", "PerfTracker",
    "get_tasks", "task_stats", "list_categories", "list_languages",
    "evaluate", "LLMJudge", "JudgeResult",
]
