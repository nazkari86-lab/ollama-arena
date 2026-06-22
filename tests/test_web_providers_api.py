"""Tests for the new /api/providers, /api/model-registry, /api/role-routing
FastAPI routes (web.py), and /api/sim/run's opt-in router_role wiring.

Mirrors tests/test_web_sim_api.py's app-construction pattern (patch
uvicorn.run to capture the built app, drive it with starlette's TestClient).
"""
from __future__ import annotations

import contextlib
import unittest.mock as mock

import pytest


@pytest.fixture(scope="module")
def _providers_app(tmp_path_factory):
    pytest.importorskip("fastapi")
    pytest.importorskip("uvicorn")

    db = tmp_path_factory.mktemp("webprovidersapi") / "arena_test.db"
    role_models_path = tmp_path_factory.mktemp("webprovidersapi_cfg") / "role_models.json"
    secrets_dir = tmp_path_factory.mktemp("webprovidersapi_secrets")
    secrets_key_path = secrets_dir / "secret.key"
    secrets_store_path = secrets_dir / "api_keys.enc.json"
    captured: dict = {}

    def _fake_uvicorn_run(app, **_kw):
        captured["app"] = app

    import ollama_arena.web as _web_mod

    with (
        mock.patch("uvicorn.run", side_effect=_fake_uvicorn_run),
        mock.patch.object(_web_mod, "_RL_DEFAULT", "10000/minute"),
        mock.patch.object(_web_mod, "_RL_MATCH", "10000/minute"),
        mock.patch(
            "ollama_arena.backends.ollama.OllamaBackend.list_models",
            return_value=["llama3", "phi3"],
        ),
    ):
        from ollama_arena.web import run_web
        run_web(host="127.0.0.1", port=19_996, db_path=str(db),
                 role_models_path=str(role_models_path),
                 secrets_key_path=str(secrets_key_path),
                 secrets_store_path=str(secrets_store_path))

    assert "app" in captured, "uvicorn.run was not called — app not built"
    return captured["app"]


@pytest.fixture(scope="module")
def client(_providers_app):
    from starlette.testclient import TestClient
    return TestClient(_providers_app, raise_server_exceptions=False)


class _RockAgent:
    def __init__(self, agent_id):
        self.agent_id = agent_id

    def act(self, obs):
        from ollama_arena.simulations.core.types import Action
        return Action(self.agent_id, "choose", {"choice": "rock"}, "")


@contextlib.contextmanager
def _no_llm_agents():
    from ollama_arena.simulations.core.runner import SimulationManager
    with mock.patch.object(
        SimulationManager, "_default_agent_factory",
        staticmethod(lambda spec, scenario: _RockAgent(spec.agent_id)),
    ):
        yield


class TestApiProviders:
    def test_lists_known_presets(self, client):
        r = client.get("/api/providers")
        assert r.status_code == 200
        names = {p["name"] for p in r.json()}
        assert {"openrouter", "opencode", "openai", "ollama", "moonshot", "zhipu"} <= names

    def test_never_exposes_key_values_only_presence_flag(self, client):
        data = client.get("/api/providers").json()
        for p in data:
            assert "key_configured" in p and isinstance(p["key_configured"], bool)
            assert "api_key" not in p and "key" not in p

    def test_classifies_local_free_and_paid(self, client):
        data = {p["name"]: p for p in client.get("/api/providers").json()}
        assert data["ollama"]["kind"] == "local"
        assert data["vllm"]["kind"] == "local"
        assert data["openrouter"]["kind"] == "free"
        assert data["opencode"]["kind"] == "free"
        assert data["openai"]["kind"] == "paid"
        assert data["moonshot"]["kind"] == "paid"


class TestApiModelRegistry:
    def test_returns_seed_entries(self, client):
        r = client.get("/api/model-registry")
        assert r.status_code == 200
        data = r.json()
        assert any(e["source"] == "openrouter_free" for e in data)
        assert any(e["source"] == "opencode_free" for e in data)

    def test_entries_carry_capability_badges(self, client):
        data = client.get("/api/model-registry").json()
        first = data[0]
        for key in ("id", "provider", "source", "free", "supports_tools",
                    "supports_json", "max_context", "cost_tier"):
            assert key in first


class TestApiRoleRouting:
    def test_get_returns_all_eight_roles_and_empty_mapping_initially(self, client):
        r = client.get("/api/role-routing")
        assert r.status_code == 200
        data = r.json()
        assert len(data["roles"]) == 8
        assert "judge" in data["roles"]
        assert data["role_models"] == {}

    def test_post_sets_a_role_then_get_reflects_it(self, client):
        r = client.post("/api/role-routing", json={"role": "npc_dialogue", "model": "qwen3:8b"})
        assert r.status_code == 200
        assert r.json()["role_models"]["npc_dialogue"] == "qwen3:8b"

        r2 = client.get("/api/role-routing")
        assert r2.json()["role_models"]["npc_dialogue"] == "qwen3:8b"

    def test_post_unknown_role_rejected(self, client):
        r = client.post("/api/role-routing", json={"role": "not_a_real_role", "model": "x"})
        assert r.status_code == 400

    def test_post_without_model_clears_the_role(self, client):
        client.post("/api/role-routing", json={"role": "judge", "model": "qwen3:8b"})
        r = client.post("/api/role-routing", json={"role": "judge"})
        assert "judge" not in r.json()["role_models"]


class TestSimRunRouterRoleWiring:
    def test_run_without_router_role_persists_no_router_role_on_agents(self, client):
        with _no_llm_agents():
            r = client.post("/api/sim/run", json={
                "scenario": "rps", "agents": ["a:1b", "b:1b"],
                "config": {"rounds": 1}, "seed": 1, "ticks": 5,
            })
        assert r.status_code == 200
        run_id = r.json()["run_id"]
        run = client.get(f"/api/sim/run/{run_id}").json()
        assert all(a.get("router_role") is None for a in run["agents"])

    def test_run_with_router_role_tags_agents_and_uses_saved_mapping(self, client):
        client.post("/api/role-routing", json={"role": "npc_dialogue", "model": "qwen3:8b"})
        with _no_llm_agents():
            r = client.post("/api/sim/run", json={
                "scenario": "rps", "agents": ["a:1b", "b:1b"],
                "config": {"rounds": 1}, "seed": 1, "ticks": 5,
                "router_role": "npc_dialogue",
            })
        assert r.status_code == 200
        run_id = r.json()["run_id"]
        run = client.get(f"/api/sim/run/{run_id}").json()
        assert all(a.get("router_role") == "npc_dialogue" for a in run["agents"])


class TestApiProviderKey:
    def test_set_key_then_providers_shows_configured(self, client):
        r = client.post("/api/providers/moonshot/key", json={"api_key": "sk-test-secret"})
        assert r.status_code == 200
        data = {p["name"]: p for p in client.get("/api/providers").json()}
        assert data["moonshot"]["key_configured"] is True

    def test_set_key_response_never_echoes_the_value(self, client):
        r = client.post("/api/providers/zhipu/key", json={"api_key": "sk-super-secret-value"})
        assert "sk-super-secret-value" not in r.text

    def test_providers_list_never_contains_any_key_value(self, client):
        client.post("/api/providers/dashscope/key", json={"api_key": "sk-another-secret"})
        listing = client.get("/api/providers").text
        assert "sk-another-secret" not in listing

    def test_clear_key_then_providers_shows_not_configured(self, client):
        client.post("/api/providers/baseten/key", json={"api_key": "sk-test"})
        r = client.delete("/api/providers/baseten/key")
        assert r.status_code == 200
        data = {p["name"]: p for p in client.get("/api/providers").json()}
        assert data["baseten"]["key_configured"] is False

    def test_set_key_unknown_provider_rejected(self, client):
        r = client.post("/api/providers/not-a-real-provider/key", json={"api_key": "x"})
        assert r.status_code == 400

    def test_set_key_for_ollama_rejected_local_runtime_needs_no_key(self, client):
        r = client.post("/api/providers/ollama/key", json={"api_key": "x"})
        assert r.status_code == 400

    def test_set_key_empty_value_rejected(self, client):
        r = client.post("/api/providers/moonshot/key", json={"api_key": ""})
        assert r.status_code == 400
