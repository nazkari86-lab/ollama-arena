"""Sandbox base types."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class Language(str, Enum):
    PYTHON     = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    RUST       = "rust"
    GO         = "go"
    CPP        = "cpp"
    BASH       = "bash"


@dataclass
class RunResult:
    accepted:   bool       = False
    output:     str        = ""
    error:      str        = ""
    exit_code:  int        = 0
    duration_s: float      = 0.0
    timed_out:  bool       = False
    blocked:    bool       = False
    language:   str        = "python"


# Aliases (lowercase strings users might type)
ALIASES: dict[str, Language] = {
    "py":         Language.PYTHON,
    "python":     Language.PYTHON,
    "python3":    Language.PYTHON,
    "js":         Language.JAVASCRIPT,
    "node":       Language.JAVASCRIPT,
    "nodejs":     Language.JAVASCRIPT,
    "javascript": Language.JAVASCRIPT,
    "ts":         Language.TYPESCRIPT,
    "typescript": Language.TYPESCRIPT,
    "rs":         Language.RUST,
    "rust":       Language.RUST,
    "go":         Language.GO,
    "golang":     Language.GO,
    "cpp":        Language.CPP,
    "c++":        Language.CPP,
    "cxx":        Language.CPP,
    "sh":         Language.BASH,
    "bash":       Language.BASH,
    "shell":      Language.BASH,
}


def normalize(lang) -> Language:
    if isinstance(lang, Language):
        return lang
    if isinstance(lang, str):
        return ALIASES.get(lang.lower(), Language.PYTHON)
    return Language.PYTHON
