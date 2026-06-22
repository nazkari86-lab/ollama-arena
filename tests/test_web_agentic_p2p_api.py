"""Tests for the /api/agentic/* and /api/p2p/* FastAPI routes
(ollama_arena/web_routes/{agentic,p2p}_routes.py).

Mirrors tests/test_web_sim_api.py's app-construction pattern (patch
uvicorn.run to capture the built app, drive it with starlette's
TestClient).
"""
from __future__ import annotations

import unittest.mock as mock

import pytest


@pytest.fixture(scope="module")
def _app(tmp_path_factory):
    pytest.importorskip("fastapi")
    pytest.importorskip("uvicorn")

    db = tmp_path_factory.mktemp("webagenticp2p") / "arena_test.db"
    captured: dict = {}

    def _fake_uvicorn_run(app, **_kw):
        captured["app"] = app

    import ollama_arena.web as _web_mod
    from ollama_arena.agentic.sandbox import SandboxBackend, SandboxConfig
    from ollama_arena.web_routes.agentic_routes import build_agentic_router as _real_build_agentic_router
    from ollama_arena.web_routes.p2p_routes import build_p2p_router as _real_build_p2p_router

    lb_path = tmp_path_factory.mktemp("p2plb") / "lb.json"
    mock_sandbox_config = SandboxConfig(backend=SandboxBackend.MOCK)

    with (
        mock.patch("uvicorn.run", side_effect=_fake_uvicorn_run),
        mock.patch.object(_web_mod, "_RL_DEFAULT", "10000/minute"),
        mock.patch.object(_web_mod, "_RL_MATCH", "10000/minute"),
        mock.patch(
            "ollama_arena.backends.ollama.OllamaBackend.list_models",
            return_value=["llama3", "phi3"],
        ),
        # Force the sandbox manager onto the deterministic MOCK backend --
        # tests must not depend on local Docker install/daemon state.
        mock.patch(
            "ollama_arena.web_routes.agentic_routes.build_agentic_router",
            side_effect=lambda *a, **kw: _real_build_agentic_router(*a, sandbox_config=mock_sandbox_config, **kw),
        ),
        # Isolate the leaderboard's storage from the real home directory
        # (GlobalLeaderboard's default ~/.ollama-arena/global_leaderboard.json
        # would otherwise read/write real user data during a test run).
        mock.patch(
            "ollama_arena.web_routes.p2p_routes.build_p2p_router",
            side_effect=lambda: _real_build_p2p_router(leaderboard_data_path=lb_path),
        ),
    ):
        from ollama_arena.web import run_web
        run_web(host="127.0.0.1", port=19_996, db_path=str(db))

    assert "app" in captured, "uvicorn.run was not called — app not built"
    return captured["app"]


@pytest.fixture(scope="module")
def client(_app):
    from starlette.testclient import TestClient
    return TestClient(_app, raise_server_exceptions=False)


# ──────────────────────────────────────────────────────────────────────────────
# Agentic — sandboxes
# ──────────────────────────────────────────────────────────────────────────────

class TestAgenticSandboxes:
    def test_list_starts_empty(self, client):
        r = client.get("/api/agentic/sandboxes")
        assert r.status_code == 200
        assert r.json() == []

    def test_start_requires_sandbox_id(self, client):
        r = client.post("/api/agentic/sandbox/start", json={})
        assert r.status_code == 400

    def test_start_creates_mock_sandbox(self, client):
        r = client.post("/api/agentic/sandbox/start", json={"sandbox_id": "qa-1"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["sandbox_id"] == "qa-1"
        assert body["status"] == "running"
        assert body["backend"] == "mock"

    def test_started_sandbox_appears_in_list(self, client):
        client.post("/api/agentic/sandbox/start", json={"sandbox_id": "qa-list"})
        r = client.get("/api/agentic/sandboxes")
        ids = {s["sandbox_id"] for s in r.json()}
        assert "qa-list" in ids

    def test_execute_requires_task(self, client):
        client.post("/api/agentic/sandbox/start", json={"sandbox_id": "qa-exec"})
        r = client.post("/api/agentic/sandbox/qa-exec/execute", json={})
        assert r.status_code == 400

    def test_execute_runs_task_in_sandbox(self, client):
        client.post("/api/agentic/sandbox/start", json={"sandbox_id": "qa-exec2"})
        r = client.post("/api/agentic/sandbox/qa-exec2/execute", json={"task": "echo hi"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["success"] is True
        assert "echo hi" in body["output"]

    def test_stop_unknown_sandbox_404s(self, client):
        r = client.post("/api/agentic/sandbox/does-not-exist/stop")
        assert r.status_code == 404

    def test_stop_known_sandbox(self, client):
        client.post("/api/agentic/sandbox/start", json={"sandbox_id": "qa-stop"})
        r = client.post("/api/agentic/sandbox/qa-stop/stop")
        assert r.status_code == 200
        assert r.json() == {"ok": True}

    def test_cleanup_removes_sandbox_from_list(self, client):
        client.post("/api/agentic/sandbox/start", json={"sandbox_id": "qa-cleanup"})
        r = client.post("/api/agentic/sandbox/qa-cleanup/cleanup")
        assert r.status_code == 200
        ids = {s["sandbox_id"] for s in client.get("/api/agentic/sandboxes").json()}
        assert "qa-cleanup" not in ids


# ──────────────────────────────────────────────────────────────────────────────
# Agentic — swarm battles
# ──────────────────────────────────────────────────────────────────────────────

class TestAgenticSwarm:
    def test_start_requires_task(self, client):
        r = client.post("/api/agentic/swarm/start", json={"mode": "2v2"})
        assert r.status_code == 400

    def test_start_rejects_invalid_mode(self, client):
        r = client.post("/api/agentic/swarm/start", json={"mode": "5v5", "task": "build a thing"})
        assert r.status_code == 400

    def test_start_404s_when_backend_unreachable(self, client):
        # is_alive() is evaluated fresh per-request (inside the route
        # handler), so it must be patched around the request itself --
        # patching only during app construction wouldn't still be active
        # by the time this call executes.
        with mock.patch("ollama_arena.backends.ollama.OllamaBackend.is_alive", return_value=False):
            r = client.post("/api/agentic/swarm/start", json={"mode": "2v2", "task": "build a thing"})
        assert r.status_code == 503

    def test_unknown_job_id_404s(self, client):
        r = client.get("/api/agentic/swarm/does-not-exist")
        assert r.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# P2P — read-only status/leaderboard/reputation
# ──────────────────────────────────────────────────────────────────────────────

class TestP2PStatus:
    def test_status_returns_stats_without_starting_networking(self, client):
        r = client.get("/api/p2p/status")
        assert r.status_code == 200
        body = r.json()
        assert body["is_running"] is False
        assert body["peer_count"] == 0
        assert "node_id" in body

    def test_leaderboard_empty_by_default(self, client):
        r = client.get("/api/p2p/leaderboard")
        assert r.status_code == 200
        body = r.json()
        assert body["entries"] == []
        assert body["stats"]["total_entries"] == 0

    def test_reputation_empty_by_default(self, client):
        r = client.get("/api/p2p/reputation")
        assert r.status_code == 200
        assert r.json() == {"nodes": []}
