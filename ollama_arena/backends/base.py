"""Backend protocol and shared types."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol, Optional


@dataclass
class GenResult:
    """Result of a single LLM generation call."""
    text:           str
    model:          str
    tokens_in:      int   = 0
    tokens_out:     int   = 0
    latency_s:      float = 0.0
    tps:            float = 0.0   # tokens/sec output
    time_to_first:  float = 0.0   # time-to-first-token
    finish_reason:  str   = "stop"
    error:          str   = ""

    @property
    def ok(self) -> bool:
        return not self.error and bool(self.text)


class Backend(Protocol):
    """Protocol every backend must implement."""

    name: str

    def generate(self, model: str, prompt: str, **opts) -> GenResult: ...
    def list_models(self) -> list[str]: ...
    def is_alive(self) -> bool: ...
