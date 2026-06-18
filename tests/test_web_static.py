"""Web static assets and export routes."""
import os
import time
import uuid

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from ollama_arena.web import run_web


@pytest.fixture(scope="module")
def client():
    import uvicorn
    captured = {}

    def fake_run(app, **_):
        captured["app"] = app

    orig = uvicorn.run
    uvicorn.run = fake_run
    try:
        run_web(host="127.0.0.1", port=0, db_path=":memory:")
    finally:
        uvicorn.run = orig

    app = captured.get("app")
    assert app is not None, "FastAPI app was not captured"
    return TestClient(app, base_url="http://localhost:7860")


def test_static_arena3d_js_returns_200(client):
    r = client.get("/static/arena3d.js")
    assert r.status_code == 200
    assert "ThreeJSArena" in r.text


def test_static_agent_trace_js_returns_200(client):
    r = client.get("/static/agent_trace.js")
    assert r.status_code == 200


def test_static_unknown_file_returns_404(client):
    r = client.get("/static/does-not-exist.js")
    assert r.status_code == 404


def test_export_royale_missing_returns_404_not_500(client):
    """sqlite3 must be imported — missing royale should 404, not NameError."""
    r = client.get("/api/export_royale/999999")
    assert r.status_code == 404


@pytest.fixture(scope="module")
def ttl_client():
    """Client with sub-second job TTL so expired jobs are pruned on next create."""
    import uvicorn
    os.environ["ARENA_JOB_TTL"] = "0.001"
    captured = {}

    def fake_run(app, **_):
        captured["app"] = app

    orig = uvicorn.run
    uvicorn.run = fake_run
    try:
        run_web(host="127.0.0.1", port=0, db_path=":memory:")
    finally:
        uvicorn.run = orig

    app = captured.get("app")
    assert app is not None
    yield TestClient(app, base_url="http://localhost:7860")
    os.environ.pop("ARENA_JOB_TTL", None)


def test_job_id_is_uuid_v4(client):
    r = client.post("/api/match", json={
        "model_a": "model-a", "model_b": "model-b",
        "category": "coding", "n": 1,
    })
    assert r.status_code == 200
    jid = r.json()["job_id"]
    parsed = uuid.UUID(jid, version=4)
    assert str(parsed) == jid


def test_expired_jobs_pruned_after_ttl(ttl_client):
    r1 = ttl_client.post("/api/match", json={
        "model_a": "a", "model_b": "b", "category": "coding", "n": 1,
    })
    jid = r1.json()["job_id"]
    time.sleep(0.02)
    ttl_client.post("/api/match", json={
        "model_a": "c", "model_b": "d", "category": "coding", "n": 1,
    })
    assert ttl_client.get(f"/api/job/{jid}").json()["status"] == "not_found"
