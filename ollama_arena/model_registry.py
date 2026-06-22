"""Provider-agnostic model registry for simulation role routing.

A single declarative table instead of free-model lists scattered across
call sites -- adding/removing/repricing a model is a data edit here (or
in a user's `model_registry.json`, merged in by `load_registry()`), never
a code change at a call site. `model_router.py` resolves each simulation
role against this table; this module owns no routing policy itself.

Seed data provenance (so it's never confused with a guess):
  - `openrouter_free` entries: fetched live from
    https://openrouter.ai/api/v1/models, filtered to ids ending in
    ":free", cross-checked against `supported_parameters` for
    supports_tools/supports_json and `context_length` for max_context.
  - `opencode_free` entries: fetched live from
    https://opencode.ai/zen/v1/models, filtered to ids ending in
    "-free". That endpoint doesn't expose context/tool-support metadata,
    so those fields are conservative defaults, not measurements.
Both were fetched 2026-06-22 -- re-running those two requests is the way
to refresh this list, not editing it from memory.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, replace

SIM_ROLES = (
    "world_step", "planner", "npc_dialogue", "narrator",
    "memory_compressor", "classifier", "judge", "fallback",
)

# Default location for a user-editable override/extension file, checked by
# load_registry() when no explicit path is given.
DEFAULT_USER_REGISTRY_PATH = os.path.expanduser("~/.config/ollama-arena/model_registry.json")


@dataclass(frozen=True)
class ModelEntry:
    id: str
    provider: str                       # preset name in OpenAICompatBackend.PRESETS, or "ollama"
    source: str                         # category tag, e.g. "openrouter_free", "opencode_free", "local"
    free: bool = True
    supports_tools: bool = False
    supports_json: bool = False
    max_context: int = 4096
    cost_tier: str = "free"             # "free" | "low" | "medium" | "high"
    role_tags: tuple[str, ...] = ()     # empty == suitable for any role
    fallback_chain: tuple[str, ...] = ()  # ids to try next, in preference order


# ── OpenRouter free models (provider="openrouter") ──────────────────────────
_OPENROUTER_FREE = [
    ModelEntry(id="qwen/qwen3-coder:free", provider="openrouter", source="openrouter_free",
               supports_tools=True, supports_json=False, max_context=1_048_576,
               fallback_chain=("qwen/qwen3-next-80b-a3b-instruct:free",)),
    ModelEntry(id="qwen/qwen3-next-80b-a3b-instruct:free", provider="openrouter", source="openrouter_free",
               supports_tools=True, supports_json=True, max_context=262_144,
               fallback_chain=("meta-llama/llama-3.3-70b-instruct:free",)),
    ModelEntry(id="meta-llama/llama-3.3-70b-instruct:free", provider="openrouter", source="openrouter_free",
               supports_tools=True, supports_json=False, max_context=131_072,
               fallback_chain=("nvidia/nemotron-nano-9b-v2:free",)),
    ModelEntry(id="nvidia/nemotron-nano-9b-v2:free", provider="openrouter", source="openrouter_free",
               supports_tools=True, supports_json=True, max_context=128_000,
               fallback_chain=("openai/gpt-oss-120b:free",)),
    ModelEntry(id="openai/gpt-oss-120b:free", provider="openrouter", source="openrouter_free",
               supports_tools=True, supports_json=False, max_context=131_072,
               fallback_chain=("openai/gpt-oss-20b:free",)),
    ModelEntry(id="openai/gpt-oss-20b:free", provider="openrouter", source="openrouter_free",
               supports_tools=True, supports_json=True, max_context=131_072,
               fallback_chain=("nousresearch/hermes-3-llama-3.1-405b:free",)),
    ModelEntry(id="nousresearch/hermes-3-llama-3.1-405b:free", provider="openrouter", source="openrouter_free",
               supports_tools=False, supports_json=False, max_context=131_072),
]

# ── OpenCode Zen free models (provider="opencode") ──────────────────────────
# Context/tool-support unmeasured (endpoint doesn't expose it) -- conservative
# defaults, treat as "probably fine for short JSON-action prompts", not a
# guarantee. Tool support is intentionally left False until verified, so the
# router never routes a tools-required role here on a false assumption.
_OPENCODE_FREE = [
    ModelEntry(id="deepseek-v4-flash-free", provider="opencode", source="opencode_free",
               max_context=32_768, fallback_chain=("qwen3.6-plus-free",)),
    ModelEntry(id="qwen3.6-plus-free", provider="opencode", source="opencode_free",
               max_context=32_768, fallback_chain=("mimo-v2.5-free",)),
    ModelEntry(id="mimo-v2.5-free", provider="opencode", source="opencode_free",
               max_context=32_768, fallback_chain=("minimax-m3-free",)),
    ModelEntry(id="minimax-m3-free", provider="opencode", source="opencode_free",
               max_context=32_768, fallback_chain=("nemotron-3-ultra-free",)),
    ModelEntry(id="nemotron-3-ultra-free", provider="opencode", source="opencode_free",
               max_context=32_768, fallback_chain=("north-mini-code-free",)),
    ModelEntry(id="north-mini-code-free", provider="opencode", source="opencode_free",
               max_context=32_768),
]

DEFAULT_REGISTRY: tuple[ModelEntry, ...] = tuple(_OPENROUTER_FREE + _OPENCODE_FREE)


def get_entry(entries, model_id: str) -> ModelEntry | None:
    for e in entries:
        if e.id == model_id:
            return e
    return None


def list_by_source(entries, source: str) -> list[ModelEntry]:
    return [e for e in entries if e.source == source]


def list_by_role(entries, role: str) -> list[ModelEntry]:
    """Entries with empty role_tags are tagged "any role" -- only entries
    that explicitly list other roles (and not this one) get filtered out."""
    return [e for e in entries if not e.role_tags or role in e.role_tags]


def _entry_from_dict(d: dict) -> ModelEntry:
    return ModelEntry(
        id=d["id"], provider=d["provider"], source=d["source"],
        free=d.get("free", True),
        supports_tools=d.get("supports_tools", False),
        supports_json=d.get("supports_json", False),
        max_context=d.get("max_context", 4096),
        cost_tier=d.get("cost_tier", "free"),
        role_tags=tuple(d.get("role_tags", ())),
        fallback_chain=tuple(d.get("fallback_chain", ())),
    )


def load_registry(extra_path: str | None = None) -> tuple[ModelEntry, ...]:
    """DEFAULT_REGISTRY, extended/overridden by a user-editable JSON file.

    This is the "easily updatable" half of the registry: adding a newly
    announced free model, or correcting a wrong max_context, is editing
    that file -- no code change, no redeploy. `extra_path` defaults to
    DEFAULT_USER_REGISTRY_PATH; a missing file is not an error (most
    installs won't have one).
    """
    path = extra_path if extra_path is not None else DEFAULT_USER_REGISTRY_PATH
    if not os.path.exists(path):
        return DEFAULT_REGISTRY

    with open(path) as f:
        raw = json.load(f)

    by_id = {e.id: e for e in DEFAULT_REGISTRY}
    for d in raw:
        entry = _entry_from_dict(d)
        by_id[entry.id] = entry
    return tuple(by_id.values())
