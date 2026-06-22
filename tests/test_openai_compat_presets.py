"""Tests for the new named-provider presets on OpenAICompatBackend.

Base URLs were verified live against each provider's own docs (not
guessed) before being added to PRESETS -- see commit message / PR
description for sources. This file pins those exact values so a future
edit can't silently drift from what was verified.
"""
from __future__ import annotations

import os
import unittest.mock as mock

from ollama_arena.backends.openai_compat import OpenAICompatBackend


class TestNewProviderPresets:
    def test_google_gemini_preset_url(self):
        b = OpenAICompatBackend(base_url="google-gemini", api_key="k")
        assert b.base == "https://generativelanguage.googleapis.com/v1beta/openai"

    def test_github_models_preset_url(self):
        b = OpenAICompatBackend(base_url="github-models", api_key="k")
        assert b.base == "https://models.github.ai/inference"

    def test_nvidia_nim_preset_url(self):
        b = OpenAICompatBackend(base_url="nvidia-nim", api_key="k")
        assert b.base == "https://integrate.api.nvidia.com/v1"

    def test_huggingface_preset_url(self):
        b = OpenAICompatBackend(base_url="huggingface-inference-providers", api_key="k")
        assert b.base == "https://router.huggingface.co/v1"

    def test_cohere_preset_url(self):
        b = OpenAICompatBackend(base_url="cohere", api_key="k")
        assert b.base == "https://api.cohere.ai/compatibility/v1"

    def test_opencode_preset_url(self):
        b = OpenAICompatBackend(base_url="opencode", api_key="k")
        assert b.base == "https://opencode.ai/zen/v1"

    def test_cloudflare_preset_substitutes_account_id_from_env(self):
        with mock.patch.dict(os.environ, {"CLOUDFLARE_ACCOUNT_ID": "acct123"}):
            b = OpenAICompatBackend(base_url="cloudflare-workers-ai", api_key="k")
        assert b.base == "https://api.cloudflare.com/client/v4/accounts/acct123/ai/v1"

    def test_cloudflare_preset_without_account_id_leaves_placeholder(self):
        env = {k: v for k, v in os.environ.items() if k != "CLOUDFLARE_ACCOUNT_ID"}
        with mock.patch.dict(os.environ, env, clear=True):
            b = OpenAICompatBackend(base_url="cloudflare-workers-ai", api_key="k")
        # No account id configured -- the URL stays templated/unusable rather
        # than silently pointing at some other host; is_alive()/generate()
        # will fail loudly instead of hitting the wrong endpoint.
        assert "{account_id}" in b.base

    def test_new_presets_have_env_key_mapping(self):
        for preset in (
            "google-gemini", "github-models", "nvidia-nim",
            "huggingface-inference-providers", "cloudflare-workers-ai", "cohere",
            "opencode",
        ):
            assert preset in OpenAICompatBackend._ENV_KEY_MAP, preset


class TestSecondBatchProviderPresets:
    """Second wave -- paid/niche providers, base URLs each verified live
    against the provider's own docs the day they were added (see
    conversation/PR for sources, not memory)."""

    def test_moonshot_preset_url(self):
        b = OpenAICompatBackend(base_url="moonshot", api_key="k")
        assert b.base == "https://api.moonshot.ai/v1"

    def test_zhipu_preset_url(self):
        b = OpenAICompatBackend(base_url="zhipu", api_key="k")
        assert b.base == "https://open.bigmodel.cn/api/paas/v4"

    def test_dashscope_preset_url(self):
        b = OpenAICompatBackend(base_url="dashscope", api_key="k")
        assert b.base == "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

    def test_baseten_preset_url(self):
        b = OpenAICompatBackend(base_url="baseten", api_key="k")
        assert b.base == "https://inference.baseten.co/v1"

    def test_hyperbolic_preset_url(self):
        b = OpenAICompatBackend(base_url="hyperbolic", api_key="k")
        assert b.base == "https://api.hyperbolic.xyz/v1"

    def test_friendli_preset_url(self):
        b = OpenAICompatBackend(base_url="friendli", api_key="k")
        assert b.base == "https://api.friendli.ai/serverless/v1"

    def test_lambda_preset_url(self):
        b = OpenAICompatBackend(base_url="lambda", api_key="k")
        assert b.base == "https://api.lambda.ai/v1"

    def test_siliconflow_preset_url(self):
        b = OpenAICompatBackend(base_url="siliconflow", api_key="k")
        assert b.base == "https://api.siliconflow.cn/v1"

    def test_upstage_preset_url(self):
        b = OpenAICompatBackend(base_url="upstage", api_key="k")
        assert b.base == "https://api.upstage.ai/v1"

    def test_vercel_ai_gateway_preset_url(self):
        b = OpenAICompatBackend(base_url="vercel-ai-gateway", api_key="k")
        assert b.base == "https://ai-gateway.vercel.sh/v1"

    def test_databricks_preset_substitutes_workspace_url_from_env(self):
        with mock.patch.dict(os.environ, {"DATABRICKS_WORKSPACE_URL": "https://my-ws.databricks.com"}):
            b = OpenAICompatBackend(base_url="databricks", api_key="k")
        assert b.base == "https://my-ws.databricks.com/serving-endpoints"

    def test_databricks_preset_without_workspace_url_leaves_placeholder(self):
        env = {k: v for k, v in os.environ.items() if k != "DATABRICKS_WORKSPACE_URL"}
        with mock.patch.dict(os.environ, env, clear=True):
            b = OpenAICompatBackend(base_url="databricks", api_key="k")
        assert "{workspace_url}" in b.base

    def test_second_batch_presets_have_env_key_mapping(self):
        for preset in (
            "moonshot", "zhipu", "dashscope", "baseten", "hyperbolic",
            "friendli", "lambda", "siliconflow", "upstage",
            "vercel-ai-gateway", "databricks",
        ):
            assert preset in OpenAICompatBackend._ENV_KEY_MAP, preset


class TestStoredKeyFallback:
    """A key saved via the Providers tab (secrets_store) is used when no
    explicit api_key arg and no env var are set -- but env vars still win
    when both are present, since they're the documented primary path."""

    def test_falls_back_to_stored_key_when_no_env_var(self, tmp_path, monkeypatch):
        from ollama_arena.secrets_store import SecretsStore
        import ollama_arena.backends.openai_compat as oc

        store = SecretsStore(key_path=str(tmp_path / "k"), store_path=str(tmp_path / "s"))
        store.set_key("moonshot", "sk-stored-value")
        monkeypatch.setattr(oc, "_secrets_store", lambda: store)
        env = {k: v for k, v in os.environ.items() if k != "MOONSHOT_API_KEY"}
        with mock.patch.dict(os.environ, env, clear=True):
            b = OpenAICompatBackend(base_url="moonshot")
        assert b.api_key == "sk-stored-value"

    def test_env_var_takes_priority_over_stored_key(self, tmp_path, monkeypatch):
        from ollama_arena.secrets_store import SecretsStore
        import ollama_arena.backends.openai_compat as oc

        store = SecretsStore(key_path=str(tmp_path / "k"), store_path=str(tmp_path / "s"))
        store.set_key("moonshot", "sk-stored-value")
        monkeypatch.setattr(oc, "_secrets_store", lambda: store)
        with mock.patch.dict(os.environ, {"MOONSHOT_API_KEY": "sk-env-value"}):
            b = OpenAICompatBackend(base_url="moonshot")
        assert b.api_key == "sk-env-value"

    def test_no_stored_key_and_no_env_falls_back_to_EMPTY(self, tmp_path, monkeypatch):
        from ollama_arena.secrets_store import SecretsStore
        import ollama_arena.backends.openai_compat as oc

        store = SecretsStore(key_path=str(tmp_path / "k"), store_path=str(tmp_path / "s"))
        monkeypatch.setattr(oc, "_secrets_store", lambda: store)
        env = {k: v for k, v in os.environ.items()
               if k not in ("MOONSHOT_API_KEY", "OPENAI_API_KEY")}
        with mock.patch.dict(os.environ, env, clear=True):
            b = OpenAICompatBackend(base_url="moonshot")
        assert b.api_key == "EMPTY"
