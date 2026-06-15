"""
Multi-language code execution sandboxes.

Supported:
  • Python      (in-process, restricted)
  • JavaScript  (node)
  • TypeScript  (ts-node or tsx)
  • Rust        (rustc)
  • Go          (go run)
  • C++         (g++/clang++)
  • Bash        (subprocess)
  • Docker mode for stronger isolation (optional)
"""
from .base import RunResult, Language
from .runner import run_in_language, available_languages

__all__ = ["RunResult", "Language", "run_in_language", "available_languages"]
