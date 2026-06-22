"""Role-based model routing for simulations.

Resolves one of the 8 simulation roles (model_registry.SIM_ROLES) to a
concrete (provider, model_id) pair: preferred (from config) -> that
model's fallback_chain -> any other free registry entry tagged for the
role -> a locally installed Ollama model (deterministic pick) -> a fixed
deterministic heuristic. `route()` is built to never raise and never
return an empty model_id -- a simulation should degrade, not crash, when
every remote free tier is unavailable.

This module only resolves *which* model to use. Building the actual
Backend object is `route_backend()`'s job, kept separate so the
resolution logic above can be unit-tested with no network access at all.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from .model_registry import ModelEntry, get_entry, list_by_role, load_registry

log = logging.getLogger("arena.model_router")

# Used only when every other stage comes up empty (no config, no registry
# entries, no local Ollama models installed) -- keeps the sim running with
# a normal "model not found" generation error instead of a router crash.
_LAST_RESORT_MODEL = "qwen2.5:0.5b"


@dataclass
class RouteResult:
    role: str
    model_id: str
    provider: str          # preset name in OpenAICompatBackend.PRESETS, or "ollama"
    source: str             # entry.source, "local", or "heuristic"
    entry: ModelEntry | None = None


def _default_local_models() -> list[str]:
    """Best-effort local Ollama model list; never raises (network down,
    Ollama not running, etc. all just mean "no local models available")."""
    try:
        from .backends.ollama import OllamaBackend
        return OllamaBackend().list_models()
    except Exception:
        return []


class RoleRouter:
    def __init__(
        self,
        registry=None,
        role_models: dict[str, str] | None = None,
        local_models=None,
        max_calls_per_role: dict[str, int] | None = None,
    ):
        self.registry = registry if registry is not None else load_registry()
        self.role_models = dict(role_models or {})
        self._local_models = local_models if local_models is not None else _default_local_models
        self._max_calls_per_role = dict(max_calls_per_role or {})
        self._call_counts: dict[str, int] = {}
        self._unavailable_until: dict[str, float] = {}

    # ── availability / lightweight circuit breaker ─────────────────────────

    def mark_unavailable(self, model_id: str, ttl_s: float = 300.0) -> None:
        self._unavailable_until[model_id] = time.monotonic() + ttl_s

    def is_available(self, model_id: str) -> bool:
        until = self._unavailable_until.get(model_id)
        return until is None or time.monotonic() >= until

    # ── quota guard ──────────────────────────────────────────────────────--

    def _quota_ok(self, role: str) -> bool:
        limit = self._max_calls_per_role.get(role)
        if limit is None:
            return True
        return self._call_counts.get(role, 0) < limit

    def _record_call(self, role: str) -> None:
        self._call_counts[role] = self._call_counts.get(role, 0) + 1

    # ── resolution ───────────────────────────────────────────────────────--

    def route(self, role: str) -> RouteResult:
        seen: set[str] = set()
        preferred = self.role_models.get(role)

        if preferred and self._quota_ok(role) and self.is_available(preferred):
            self._record_call(role)
            entry = get_entry(self.registry, preferred)
            return RouteResult(
                role=role, model_id=preferred,
                provider=entry.provider if entry else "ollama",
                source=entry.source if entry else "local", entry=entry,
            )

        preferred_entry = get_entry(self.registry, preferred) if preferred else None
        if preferred:
            seen.add(preferred)

        chain = list(preferred_entry.fallback_chain) if preferred_entry else []
        while chain:
            cand = chain.pop(0)
            if cand in seen:
                continue
            seen.add(cand)
            cand_entry = get_entry(self.registry, cand)
            if cand_entry is None:
                continue
            if not self.is_available(cand):
                chain.extend(cand_entry.fallback_chain)
                continue
            self._record_call(role)
            return RouteResult(
                role=role, model_id=cand, provider=cand_entry.provider,
                source=cand_entry.source, entry=cand_entry,
            )

        for cand_entry in list_by_role(self.registry, role):
            if cand_entry.id in seen or not cand_entry.free:
                continue
            seen.add(cand_entry.id)
            if not self.is_available(cand_entry.id):
                continue
            self._record_call(role)
            return RouteResult(
                role=role, model_id=cand_entry.id, provider=cand_entry.provider,
                source=cand_entry.source, entry=cand_entry,
            )

        for model_id in sorted(self._local_models()):
            if not self.is_available(model_id):
                continue
            self._record_call(role)
            return RouteResult(role=role, model_id=model_id, provider="ollama", source="local")

        self._record_call(role)
        return RouteResult(
            role=role, model_id=preferred or _LAST_RESORT_MODEL,
            provider="ollama", source="heuristic",
        )


def route_backend(router: RoleRouter, role: str, ollama_url: str = "http://localhost:11434",
                   backend_builder=None):
    """Resolve a role and build the actual Backend for it.

    `backend_builder(provider, ollama_url) -> Backend` defaults to real
    construction; tests inject a fake to avoid touching the network.
    """
    result = router.route(role)
    if backend_builder is not None:
        backend = backend_builder(result.provider, ollama_url)
    elif result.provider == "ollama":
        from .backends.auto import auto_backend
        backend = auto_backend(ollama_url)
    else:
        from .backends.openai_compat import OpenAICompatBackend
        backend = OpenAICompatBackend(base_url=result.provider)
    return backend, result.model_id
