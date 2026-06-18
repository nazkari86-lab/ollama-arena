"""Backend protocol + shared text utilities."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol, Optional

# ── Thinking-token stripping ──────────────────────────────────────────────────
# Many local models emit reasoning/chain-of-thought blocks in various formats.
# We strip them all before showing output to users or scoring responses.
_THINK_PATTERNS = [
    # DeepSeek-R1, Qwen3, QwQ: <think>...</think>
    re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE),
    # Some fine-tunes: <thinking>...</thinking>
    re.compile(r"<thinking>.*?</thinking>", re.DOTALL | re.IGNORECASE),
    # Reasoning block: <reasoning>...</reasoning>
    re.compile(r"<reasoning>.*?</reasoning>", re.DOTALL | re.IGNORECASE),
    # Custom channel-style: <|channel>thought\n<channel|>...
    # Captures everything from the channel marker until either the next
    # <|channel>answer marker (exclusive) or end of string, then removes
    # the answer marker too so only the final text remains.
    re.compile(r"<\|channel>thought.*?<channel\|>.*?(?=<\|channel>answer|$)", re.DOTALL | re.IGNORECASE),
    re.compile(r"<\|channel>answer\s*\n?<channel\|>", re.DOTALL | re.IGNORECASE),
    # Generic <|channel>NAME\n<channel|> delimiters (removes any channel header)
    re.compile(r"<\|channel>[^\n]*\n<channel\|>", re.IGNORECASE),
    # Llama-style [INST] that sometimes leaks: strip only the tag, not the content
    re.compile(r"\[/?INST\]", re.IGNORECASE),
]


def strip_thinking(text: str) -> str:
    """Remove all thinking/reasoning blocks from model output."""
    for pat in _THINK_PATTERNS:
        text = pat.sub("", text)
    return text.strip()


# ── Date-aware system prompt ──────────────────────────────────────────────────
_DATE_SYSTEM = (
    "You are a helpful, accurate assistant.\n"
    "IMPORTANT: Today's date is {date}.\n"
    "When asked about the current date, time, or recent events, use {date} as the reference.\n"
    "Your training data has a knowledge cutoff in the past — clearly state this when relevant, "
    "but never substitute your cutoff date for today's actual date."
)


def system_message_with_date() -> dict:
    today = date.today().isoformat()
    return {"role": "system", "content": _DATE_SYSTEM.format(date=today)}


def inject_system(messages: list[dict]) -> list[dict]:
    """Prepend date-aware system message unless the caller already supplied one."""
    if messages and messages[0].get("role") == "system":
        return messages
    return [system_message_with_date()] + list(messages)


@dataclass
class ChatTurnResult:
    """Single chat completion turn (content and/or tool_calls)."""
    text:          str = ""
    tool_calls:    list = field(default_factory=list)
    tokens_in:     int = 0
    tokens_out:    int = 0
    latency_s:     float = 0.0
    time_to_first: float = 0.0
    finish_reason: str = "stop"
    error:         str = ""


@dataclass
class GenResult:
    text:             str
    model:            str
    tokens_in:        int   = 0
    tokens_out:       int   = 0
    latency_s:        float = 0.0
    tps:              float = 0.0    # output tokens / second
    time_to_first:    float = 0.0
    finish_reason:    str   = "stop"
    error:            str   = ""
    spec_accept_rate: float = 0.0   # draft token acceptance rate (0–1)
    backend_type:     str   = ""    # "speculative", "ollama", "openai-compat", …
    tool_calls:       list  = field(default_factory=list)
    agent_trace:      list  = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.error and bool(
            self.text or self.tool_calls or self.agent_trace
        )


class Backend(Protocol):
    name: str

    def generate(self, model: str, prompt: str, **opts) -> GenResult: ...
    def generate_with_tools(self, model: str, messages: list[dict], tools: list[dict], **opts) -> GenResult: ...
    def list_models(self) -> list[str]: ...
    def is_alive(self) -> bool: ...
