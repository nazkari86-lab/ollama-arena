"""ollama-arena — Local LLM ELO Arena for Ollama models."""
__version__ = "1.0.0"
__author__  = "nazkari86-lab"

from .arena import Arena, OllamaClient, MatchResult
from .elo import EloStore
from .tasks import get_tasks, task_stats, list_categories

__all__ = [
    "Arena", "OllamaClient", "MatchResult",
    "EloStore", "get_tasks", "task_stats", "list_categories",
]
