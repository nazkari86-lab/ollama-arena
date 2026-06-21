"""Tests for the /api/sim/* FastAPI routes (web.py's "Simulations API" block).

Mirrors tests/test_web_api.py's app-construction pattern (patch uvicorn.run to
capture the built app, drive it with starlette's TestClient). The rps
scenario's default LLMSimAgent would otherwise hit a real Ollama backend, so
every test that actually starts a run patches SimulationManager's
_default_agent_factory to a scripted rock-playing agent instead -- the same
no-LLM-calls-needed trick tests/test_cli_sim_cmd.py uses via an injected
agent_factory, just applied at the class level since the web routes
construct their own SimulationManager() instances inline.
"""
from __future__ import annotations

import contextlib
import unittest.mock as mock

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def _sim_app(tmp_path_factory):
    """Build the FastAPI app once for the whole module."""
    pytest.importorskip("fastapi")
    pytest.importorskip("uvicorn")

    db = tmp_path_factory.mktemp("websimapi") / "arena_test.db"
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
        run_web(host="127.0.0.1", port=19_997, db_path=str(db))

    assert "app" in captured, "uvicorn.run was not called — app not built"
    return captured["app"]


@pytest.fixture(scope="module")
def client(_sim_app):
    from starlette.testclient import TestClient
    return TestClient(_sim_app, raise_server_exceptions=False)


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
            "scenario": "rps", "agents": list(agents),
            "config": {"rounds": 3}, "seed": 1, "ticks": ticks,
        })
    assert r.status_code == 200, r.text
    return r.json()["run_id"]


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/sim/scenarios
# ──────────────────────────────────────────────────────────────────────────────

class TestSimScenarios:
    def test_lists_registered_scenarios(self, client):
        r = client.get("/api/sim/scenarios")
        assert r.status_code == 200
        names = {s["name"] for s in r.json()}
        assert "rps" in names
        assert "mafia" in names
        assert "tictactoe" in names

    def test_each_entry_has_description(self, client):
        data = client.get("/api/sim/scenarios").json()
        assert all(isinstance(s["description"], str) and s["description"] for s in data)


class TestSimRunsList:
    def test_runs_list_includes_started_run(self, client):
        run_id = _start_rps_run(client)
        runs = client.get("/api/sim/runs").json()
        assert any(r["run_id"] == run_id for r in runs)

    def test_runs_list_filters_by_scenario(self, client):
        _start_rps_run(client)
        runs = client.get("/api/sim/runs?scenario=rps").json()
        assert all(r["scenario"] == "rps" for r in runs)
        assert client.get("/api/sim/runs?scenario=does_not_exist").json() == []


class TestSimCompare:
    def test_compare_two_runs_reports_metrics(self, client):
        run_a = _start_rps_run(client)
        run_b = _start_rps_run(client)
        r = client.get(f"/api/sim/compare?run_ids={run_a},{run_b}")
        assert r.status_code == 200
        data = r.json()
        assert set(data["run_ids"]) == {run_a, run_b}
        assert data["scenario"] == "rps"
        assert isinstance(data["best_run_by_metric"], dict)

    def test_compare_rejects_empty_run_ids(self, client):
        r = client.get("/api/sim/compare?run_ids=")
        assert r.status_code == 400


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/sim/run, GET /api/sim/run/{id}, GET .../replay
# ──────────────────────────────────────────────────────────────────────────────

class TestSimRunLifecycle:
    def test_run_rejects_missing_agents(self, client):
        r = client.post("/api/sim/run", json={"scenario": "rps", "agents": []})
        assert r.status_code == 400

    def test_run_rejects_unknown_scenario(self, client):
        with _no_llm_agents():
            r = client.post("/api/sim/run", json={
                "scenario": "does_not_exist", "agents": ["a:1b", "b:1b"],
            })
        assert r.status_code == 404

    def test_run_completes_and_is_inspectable(self, client):
        run_id = _start_rps_run(client)

        r = client.get(f"/api/sim/run/{run_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["scenario"] == "rps"
        assert data["status"] == "completed"
        assert {a["agent_id"] for a in data["agents"]} == {"a:1b", "b:1b"}
        assert isinstance(data["metrics"], dict)

    def test_run_replay_contains_round_results(self, client):
        run_id = _start_rps_run(client)
        r = client.get(f"/api/sim/run/{run_id}/replay")
        assert r.status_code == 200
        kinds = {e["kind"] for e in r.json()}
        assert "round_result" in kinds

    def test_run_replay_with_tick_filters_events(self, client):
        run_id = _start_rps_run(client)
        all_events = client.get(f"/api/sim/run/{run_id}/replay").json()
        max_tick = max(e["tick"] for e in all_events)
        filtered = client.get(f"/api/sim/run/{run_id}/replay?tick=0").json()
        assert all(e["tick"] <= 0 for e in filtered)
        assert len(filtered) <= len(all_events)
        assert max_tick >= 0

    def test_run_trace_contains_actions_and_events(self, client):
        run_id = _start_rps_run(client)
        r = client.get(f"/api/sim/run/{run_id}/trace")
        assert r.status_code == 200
        data = r.json()
        assert data["run"]["run_id"] == run_id
        assert data["transitions"]
        assert data["transitions"][0]["action"]["kind"] == "choose"
        assert data["events"][0]["kind"] == "round_result"

    def test_get_unknown_run_404(self, client):
        r = client.get("/api/sim/run/does-not-exist")
        assert r.status_code == 404

    def test_replay_unknown_run_returns_empty_list(self, client):
        r = client.get("/api/sim/run/does-not-exist/replay")
        assert r.status_code == 200
        assert r.json() == []


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/sim/run/{id}/pause and /resume
# ──────────────────────────────────────────────────────────────────────────────

class TestSimPauseResume:
    def test_pause_unknown_run_404(self, client):
        r = client.post("/api/sim/run/does-not-exist/pause")
        assert r.status_code == 404

    def test_pause_known_run_sets_status(self, client):
        run_id = _start_rps_run(client)
        r = client.post(f"/api/sim/run/{run_id}/pause")
        assert r.status_code == 200
        assert r.json()["status"] == "paused"
        assert client.get(f"/api/sim/run/{run_id}").json()["status"] == "paused"

    def test_resume_unknown_run_404(self, client):
        r = client.post("/api/sim/run/does-not-exist/resume", json={})
        assert r.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/sim/train -- broadcasts sim_training_progress over /ws
# ──────────────────────────────────────────────────────────────────────────────

class TestSimTrain:
    def test_train_on_unknown_run_reports_error_via_websocket(self, client):
        with client.websocket_connect("/ws") as ws:
            r = client.post("/api/sim/train", json={"run_id": "does-not-exist", "epochs": 2})
            assert r.status_code == 200
            started = ws.receive_json()
            finished = ws.receive_json()
        assert started["type"] == "sim_training_progress"
        assert started["status"] == "started"
        assert finished["status"] == "error"
        assert "no transitions" in finished["error"]

    def test_train_missing_run_id_400(self, client):
        r = client.post("/api/sim/train", json={})
        assert r.status_code == 400

    def test_train_single_action_kind_reports_failure_not_crash(self, client):
        """rps with both agents always playing rock produces only one action
        kind ('choose') -- train_imitation() correctly refuses (needs >= 2
        kinds to classify); the route must report this via the broadcast,
        not let the ValueError escape as an uncaught 500 in the background
        thread."""
        pytest.importorskip("torch")
        run_id = _start_rps_run(client)
        with client.websocket_connect("/ws") as ws:
            r = client.post("/api/sim/train", json={"run_id": run_id, "epochs": 2})
            assert r.status_code == 200
            started = ws.receive_json()
            finished = ws.receive_json()
        assert started["status"] == "started"
        assert finished["status"] == "error"
        assert "distinct action kinds" in finished["error"]
