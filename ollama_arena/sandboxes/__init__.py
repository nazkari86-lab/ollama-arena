"""
Multi-language sandboxed code execution.

Languages: python, javascript, typescript, rust, go, cpp, bash.
Set use_docker=True for an isolated container with --network=none.
"""
from .base import RunResult, Language
from .runner import run_in_language, available_languages

__all__ = ["RunResult", "Language", "run_in_language", "available_languages"]
