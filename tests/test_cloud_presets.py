"""Cloud provider presets — verify resolution + per-preset env-var lookup."""
import os
import pytest

from ollama_arena.backends.openai_compat import OpenAICompatBackend


CLOUD_PRESETS = [
    ("deepseek",   "DEEPSEEK_API_KEY",   "https://api.deepseek.com/v1"),
    ("xai",        "XAI_API_KEY",        "https://api.x.ai/v1"),
    ("grok",       "XAI_API_KEY",        "https://api.x.ai/v1"),
    ("cerebras",   "CEREBRAS_API_KEY",   "https://api.cerebras.ai/v1"),
    ("anthropic",  "ANTHROPIC_API_KEY",  "https://api.anthropic.com/v1"),
    ("mistral",    "MISTRAL_API_KEY",    "https://api.mistral.ai/v1"),
    ("perplexity", "PERPLEXITY_API_KEY", "https://api.perplexity.ai"),
    ("sambanova",  "SAMBANOVA_API_KEY",  "https://api.sambanova.ai/v1"),
    ("novita",     "NOVITA_API_KEY",     "https://api.novita.ai/v3/openai"),
]


@pytest.mark.parametrize("name,env_key,expected_base", CLOUD_PRESETS)
def test_preset_resolves_to_endpoint(name, env_key, expected_base, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv(env_key, f"test-{name}-key")
    b = OpenAICompatBackend(base_url=name)
    assert b.base == expected_base
    assert b.api_key == f"test-{name}-key"


def test_preset_falls_back_to_openai_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "fallback-key")
    b = OpenAICompatBackend(base_url="deepseek")
    assert b.api_key == "fallback-key"


def test_explicit_api_key_overrides_env(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "from-env")
    b = OpenAICompatBackend(base_url="xai", api_key="from-arg")
    assert b.api_key == "from-arg"


def test_unknown_url_is_kept_verbatim():
    b = OpenAICompatBackend(base_url="https://custom.example.com/v1",
                            api_key="x")
    assert b.base == "https://custom.example.com/v1"
