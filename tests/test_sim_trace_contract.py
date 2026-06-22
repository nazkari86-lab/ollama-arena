"""Pins the exact JSON shape of GET /api/sim/run/{id}/trace that the Godot
World renderer (godot_world/scripts/world_renderer.gd) depends on. If this
test needs to change, world_renderer.gd's HTTPRequest response parsing needs
a matching change.
"""
from __future__ import annotations

import contextlib
import unittest.mock as mock

import pytest


@pytest.fixture(scope="module")
def _trace_app(tmp_path_factory):
    pytest.importorskip("fastapi")
    pytest.importorskip("uvicorn")

    db = tmp_path_factory.mktemp("simtracecontract") / "arena_test.db"
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
        run_web(host="127.0.0.1", port=19_995, db_path=str(db))

    assert "app" in captured, "uvicorn.run was not called — app not built"
    return captured["app"]


@pytest.fixture(scope="module")
def client(_trace_app):
    from starlette.testclient import TestClient
    return TestClient(_trace_app, raise_server_exceptions=False)


class _RockAgent:
    """A scripted SimAgent that always plays rock -- avoids real LLM calls."""

    def __init__(self, agent_id):
        self.agent_id = agent_id

    def act(self, obs):
        from ollama_arena.simulations.core.types import Action
        return Action(self.agent_id, "choose", {"choice": "rock"}, "")


@contextlib.contextmanager
def _no_llm_agents():
    """Patch SimulationManager's default agent factory so every
    SimulationManager() constructed inside web.py's routes (which don't
    accept an agent_factory override) uses scripted rock-agents instead of
    real LLMSimAgent backends."""
    from ollama_arena.simulations.core.runner import SimulationManager
    with mock.patch.object(
        SimulationManager, "_default_agent_factory",
        staticmethod(lambda spec, scenario: _RockAgent(spec.agent_id)),
    ):
        yield


def _start_rps_run(client, agents=("a:1b", "b:1b"), ticks=10):
    with _no_llm_agents():
        r = client.post("/api/sim/run", json={
            "scenario": "rps", "agents": list(agents), "ticks": ticks,
        })
    assert r.status_code == 200, r.text
    return r.json()["run_id"]


def test_trace_top_level_shape(client):
    run_id = _start_rps_run(client)
    r = client.get(f"/api/sim/run/{run_id}/trace")
    assert r.status_code == 200
    data = r.json()
    assert set(data.keys()) == {"run", "transitions", "events"}


def test_trace_run_field_has_scenario_and_agents(client):
    run_id = _start_rps_run(client)
    data = client.get(f"/api/sim/run/{run_id}/trace").json()
    run = data["run"]
    assert run["run_id"] == run_id
    assert run["scenario"] == "rps"
    assert isinstance(run["agents"], list)
    assert {"agent_id", "model", "config"} <= set(run["agents"][0].keys())


def test_trace_event_shape_has_visibility_field(client):
    run_id = _start_rps_run(client)
    data = client.get(f"/api/sim/run/{run_id}/trace").json()
    assert data["events"], "expected at least one event"
    event = data["events"][0]
    assert set(event.keys()) == {"id", "tick", "kind", "payload", "actor_id", "visibility"}
    assert event["visibility"] in ("public", "private")


def test_trace_unknown_run_404s(client):
    r = client.get("/api/sim/run/does-not-exist/trace")
    assert r.status_code == 404
