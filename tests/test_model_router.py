"""Tests for ollama_arena.model_router.RoleRouter.

Pure resolution logic only -- no real network calls. `local_models` and
`backend_builder` are injected fakes so the fallback chain (preferred ->
fallback_chain -> any free entry for the role -> local Ollama ->
deterministic heuristic) can be exercised deterministically.
"""
from __future__ import annotations

from ollama_arena.model_registry import ModelEntry
from ollama_arena.model_router import RoleRouter, RouteResult


def _registry():
    return [
        ModelEntry(id="primary:free", provider="openrouter", source="openrouter_free",
                   fallback_chain=("secondary:free",)),
        ModelEntry(id="secondary:free", provider="openrouter", source="openrouter_free",
                   fallback_chain=("tertiary:free",)),
        ModelEntry(id="tertiary:free", provider="opencode", source="opencode_free"),
        ModelEntry(id="any-role:free", provider="opencode", source="opencode_free"),
    ]


class TestPreferredRoute:
    def test_returns_configured_model_for_role(self):
        router = RoleRouter(registry=_registry(), role_models={"judge": "primary:free"},
                             local_models=lambda: [])
        result = router.route("judge")
        assert result.model_id == "primary:free"
        assert result.provider == "openrouter"
        assert result.source == "openrouter_free"

    def test_role_with_no_config_skips_to_other_stages(self):
        router = RoleRouter(registry=_registry(), role_models={}, local_models=lambda: ["llama3:8b"])
        result = router.route("npc_dialogue")
        # No preferred, no fallback chain to walk -- lands on a free
        # registry entry or local model, never raises.
        assert result.model_id


class TestFallbackChain:
    def test_walks_to_secondary_when_primary_unavailable(self):
        router = RoleRouter(registry=_registry(), role_models={"judge": "primary:free"},
                             local_models=lambda: [])
        router.mark_unavailable("primary:free")
        result = router.route("judge")
        assert result.model_id == "secondary:free"

    def test_walks_multiple_hops_when_several_unavailable(self):
        router = RoleRouter(registry=_registry(), role_models={"judge": "primary:free"},
                             local_models=lambda: [])
        router.mark_unavailable("primary:free")
        router.mark_unavailable("secondary:free")
        result = router.route("judge")
        assert result.model_id == "tertiary:free"

    def test_never_revisits_a_seen_id_even_with_a_fallback_cycle(self):
        cyclic = [
            ModelEntry(id="a:free", provider="openrouter", source="openrouter_free",
                       fallback_chain=("b:free",)),
            ModelEntry(id="b:free", provider="openrouter", source="openrouter_free",
                       fallback_chain=("a:free",)),
        ]
        router = RoleRouter(registry=cyclic, role_models={"judge": "a:free"},
                            local_models=lambda: [])
        router.mark_unavailable("a:free")
        router.mark_unavailable("b:free")
        result = router.route("judge")  # both unavailable -- must not infinite-loop
        assert result.model_id  # falls through to heuristic, doesn't hang/raise


class TestLocalFallback:
    def test_falls_back_to_local_when_registry_exhausted(self):
        router = RoleRouter(registry=[], role_models={}, local_models=lambda: ["qwen3:8b", "llama3:8b"])
        result = router.route("planner")
        assert result.provider == "ollama"
        assert result.source == "local"
        assert result.model_id == "llama3:8b"  # deterministic: sorted, first alphabetically

    def test_never_raises_when_everything_is_empty(self):
        router = RoleRouter(registry=[], role_models={}, local_models=lambda: [])
        result = router.route("fallback")
        assert isinstance(result, RouteResult)
        assert result.model_id  # always something, never None/empty


class TestQuotaGuard:
    def test_exceeding_max_calls_per_role_skips_preferred(self):
        router = RoleRouter(registry=_registry(), role_models={"judge": "primary:free"},
                            local_models=lambda: [], max_calls_per_role={"judge": 1})
        first = router.route("judge")
        assert first.model_id == "primary:free"
        second = router.route("judge")
        assert second.model_id != "primary:free"


class TestAvailability:
    def test_is_available_true_by_default(self):
        router = RoleRouter(registry=[], role_models={}, local_models=lambda: [])
        assert router.is_available("anything") is True

    def test_marking_unavailable_then_available_again_after_ttl(self, monkeypatch):
        import ollama_arena.model_router as mr
        t = [1000.0]
        monkeypatch.setattr(mr.time, "monotonic", lambda: t[0])
        router = RoleRouter(registry=[], role_models={}, local_models=lambda: [])
        router.mark_unavailable("m", ttl_s=10.0)
        assert router.is_available("m") is False
        t[0] += 11.0
        assert router.is_available("m") is True
