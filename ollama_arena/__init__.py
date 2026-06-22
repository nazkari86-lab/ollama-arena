"""Pair-wise evaluation arena for local LLMs."""
__version__ = "3.2.0"

from .arena import Arena, MatchResult
from .backends import Backend, OllamaBackend, OpenAICompatBackend, GenResult
from .elo import EloStore, update_elo
from .performance import PerfTracker
from .tasks import get_tasks, task_stats, list_categories, list_languages
from .evaluator import evaluate
from .judge import LLMJudge, JudgeResult

__all__ = [
    "Arena", "MatchResult",
    "Backend", "OllamaBackend", "OpenAICompatBackend", "GenResult",
    "EloStore", "update_elo", "PerfTracker",
    "get_tasks", "task_stats", "list_categories", "list_languages",
    "evaluate", "LLMJudge", "JudgeResult",
]
