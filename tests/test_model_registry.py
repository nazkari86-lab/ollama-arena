"""Tests for ollama_arena.model_registry — the provider-agnostic model
table the router (model_router.py) resolves roles against.

Seed entries are pinned to real, live-verified data (OpenRouter
/api/v1/models and OpenCode Zen /v1/models, fetched the day this was
written) rather than guessed model names -- see the comments next to
DEFAULT_REGISTRY in the module itself for the exact source.
"""
from __future__ import annotations

import json

from ollama_arena.model_registry import (
    SIM_ROLES,
    ModelEntry,
    DEFAULT_REGISTRY,
    get_entry,
    list_by_role,
    list_by_source,
    load_registry,
)


class TestModelEntry:
    def test_defaults(self):
        e = ModelEntry(id="m", provider="ollama", source="local")
        assert e.free is True
        assert e.supports_tools is False
        assert e.role_tags == ()
        assert e.fallback_chain == ()


class TestDefaultRegistrySeed:
    def test_seed_entries_have_unique_ids(self):
        ids = [e.id for e in DEFAULT_REGISTRY]
        assert len(ids) == len(set(ids))

    def test_seed_includes_openrouter_free_models(self):
        sources = {e.source for e in DEFAULT_REGISTRY}
        assert "openrouter_free" in sources

    def test_seed_includes_opencode_free_models(self):
        sources = {e.source for e in DEFAULT_REGISTRY}
        assert "opencode_free" in sources

    def test_every_seed_entry_is_actually_free(self):
        for e in DEFAULT_REGISTRY:
            assert e.free is True, e.id

    def test_every_seed_entry_has_a_known_provider_preset(self):
        from ollama_arena.backends.openai_compat import OpenAICompatBackend
        for e in DEFAULT_REGISTRY:
            assert e.provider in OpenAICompatBackend.PRESETS, e.id


class TestLookupHelpers:
    def test_get_entry_found(self):
        first = DEFAULT_REGISTRY[0]
        assert get_entry(DEFAULT_REGISTRY, first.id) is first

    def test_get_entry_missing_returns_none(self):
        assert get_entry(DEFAULT_REGISTRY, "nonexistent/model:free") is None

    def test_list_by_source(self):
        result = list_by_source(DEFAULT_REGISTRY, "openrouter_free")
        assert result
        assert all(e.source == "openrouter_free" for e in result)

    def test_list_by_role_empty_role_tags_match_any_role(self):
        entries = [ModelEntry(id="a", provider="ollama", source="local")]
        assert list_by_role(entries, "judge") == entries

    def test_list_by_role_filters_to_tagged_role_only(self):
        entries = [
            ModelEntry(id="a", provider="ollama", source="local", role_tags=("judge",)),
            ModelEntry(id="b", provider="ollama", source="local", role_tags=("planner",)),
        ]
        assert [e.id for e in list_by_role(entries, "judge")] == ["a"]


class TestSimRoles:
    def test_eight_roles_defined(self):
        assert len(SIM_ROLES) == 8
        assert SIM_ROLES == (
            "world_step", "planner", "npc_dialogue", "narrator",
            "memory_compressor", "classifier", "judge", "fallback",
        )


class TestLoadRegistryUserOverride:
    def test_user_file_adds_new_entry(self, tmp_path):
        user_file = tmp_path / "model_registry.json"
        user_file.write_text(json.dumps([
            {"id": "my-custom/model:free", "provider": "openrouter",
             "source": "openrouter_free", "free": True},
        ]))
        entries = load_registry(extra_path=str(user_file))
        assert get_entry(entries, "my-custom/model:free") is not None
        # Defaults are still present -- user file extends, doesn't replace.
        assert get_entry(entries, DEFAULT_REGISTRY[0].id) is not None

    def test_user_file_overrides_existing_id(self, tmp_path):
        target = DEFAULT_REGISTRY[0]
        user_file = tmp_path / "model_registry.json"
        user_file.write_text(json.dumps([
            {"id": target.id, "provider": target.provider,
             "source": target.source, "free": True, "max_context": 999999},
        ]))
        entries = load_registry(extra_path=str(user_file))
        overridden = get_entry(entries, target.id)
        assert overridden.max_context == 999999

    def test_missing_user_file_is_not_an_error(self, tmp_path):
        entries = load_registry(extra_path=str(tmp_path / "does_not_exist.json"))
        assert entries == DEFAULT_REGISTRY

    def test_no_path_returns_defaults_only(self):
        assert load_registry() == DEFAULT_REGISTRY
