"""Tests for ollama_arena.secrets_store -- encrypted local storage for
user-entered provider API keys.

Every test uses tmp_path-scoped key/store files, never the real
~/.config/ollama-arena -- a SecretsStore instance is always constructed
with explicit paths.
"""
from __future__ import annotations

import os
import stat

import pytest

from ollama_arena.secrets_store import SecretsStore


@pytest.fixture
def store(tmp_path):
    return SecretsStore(
        key_path=str(tmp_path / "secret.key"),
        store_path=str(tmp_path / "api_keys.enc.json"),
    )


class TestSetAndGet:
    def test_round_trips_a_value(self, store):
        store.set_key("openrouter", "sk-test-123")
        assert store.get_key("openrouter") == "sk-test-123"

    def test_unknown_provider_returns_none(self, store):
        assert store.get_key("never-set") is None

    def test_has_key_reflects_presence_not_value(self, store):
        assert store.has_key("openrouter") is False
        store.set_key("openrouter", "sk-test-123")
        assert store.has_key("openrouter") is True

    def test_clear_key_removes_it(self, store):
        store.set_key("openrouter", "sk-test-123")
        store.clear_key("openrouter")
        assert store.get_key("openrouter") is None
        assert store.has_key("openrouter") is False

    def test_clear_key_on_unset_provider_is_a_noop(self, store):
        store.clear_key("never-set")  # must not raise

    def test_configured_providers_lists_only_presence(self, store):
        store.set_key("openrouter", "a")
        store.set_key("moonshot", "b")
        assert store.configured_providers() == {"openrouter", "moonshot"}


class TestEncryptionAtRest:
    def test_store_file_never_contains_the_plaintext_value(self, store, tmp_path):
        store.set_key("openrouter", "sk-super-secret-value")
        raw = (tmp_path / "api_keys.enc.json").read_text()
        assert "sk-super-secret-value" not in raw

    def test_store_file_is_owner_only_permissions(self, store, tmp_path):
        store.set_key("openrouter", "sk-test-123")
        mode = stat.S_IMODE(os.stat(tmp_path / "api_keys.enc.json").st_mode)
        assert mode == 0o600

    def test_key_file_is_owner_only_permissions(self, store, tmp_path):
        store.set_key("openrouter", "sk-test-123")
        mode = stat.S_IMODE(os.stat(tmp_path / "secret.key").st_mode)
        assert mode == 0o600

    def test_different_stores_sharing_a_key_file_can_decrypt_each_others_values(self, tmp_path):
        """Same key_path, same store_path -- this is just "the persistence
        round-trips across separate SecretsStore instances," the normal
        case of one process writing and a later process (or request)
        reading."""
        key_path, store_path = str(tmp_path / "k"), str(tmp_path / "s")
        SecretsStore(key_path=key_path, store_path=store_path).set_key("openrouter", "abc")
        reopened = SecretsStore(key_path=key_path, store_path=store_path)
        assert reopened.get_key("openrouter") == "abc"

    def test_corrupted_store_file_does_not_raise_returns_none(self, store, tmp_path):
        store.set_key("openrouter", "sk-test-123")
        (tmp_path / "api_keys.enc.json").write_text("not json{{{")
        assert store.get_key("openrouter") is None


class TestSecretsUnavailable:
    def test_missing_cryptography_raises_clear_error_on_set(self, store, monkeypatch):
        """_get_fernet() is the one place that converts a missing
        `cryptography` package into SecretsUnavailable -- simulate that
        exact contract rather than bypassing it."""
        import ollama_arena.secrets_store as mod

        def _boom(*a, **k):
            raise mod.SecretsUnavailable("no cryptography")

        monkeypatch.setattr(mod, "_get_fernet", _boom)
        with pytest.raises(mod.SecretsUnavailable):
            store.set_key("openrouter", "x")

    def test_missing_cryptography_get_key_returns_none_not_raise(self, store, monkeypatch):
        import ollama_arena.secrets_store as mod
        store.set_key("openrouter", "x")

        def _boom(*a, **k):
            raise mod.SecretsUnavailable("no cryptography")

        monkeypatch.setattr(mod, "_get_fernet", _boom)
        assert store.get_key("openrouter") is None


class TestModuleLevelDefaultStore:
    def test_module_functions_use_injectable_default_paths(self, tmp_path, monkeypatch):
        import ollama_arena.secrets_store as mod
        monkeypatch.setattr(mod, "_DEFAULT_KEY_PATH", str(tmp_path / "k"))
        monkeypatch.setattr(mod, "_DEFAULT_STORE_PATH", str(tmp_path / "s"))
        monkeypatch.setattr(mod, "_default_store", None)

        mod.set_key("openrouter", "sk-abc")
        assert mod.has_key("openrouter")
        assert mod.get_key("openrouter") == "sk-abc"
        mod.clear_key("openrouter")
        assert not mod.has_key("openrouter")
