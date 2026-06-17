"""Web hardening — CORS, security headers, rate limits, WebSocket origin check."""
import os
import pytest

# Tell the app: only this origin is allowed
os.environ["ARENA_ALLOWED_ORIGINS"] = "http://localhost:7860"
os.environ["ARENA_RL_PLAYGROUND"]   = "3/minute"
# Tight default limit so we can verify rate limiting fires on /api/version
os.environ["ARENA_RL_DEFAULT"]      = "5/minute"

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from ollama_arena.web import run_web


# Build the app without actually running uvicorn. We monkey-patch
# uvicorn.run so the call returns immediately and we can grab the app.
@pytest.fixture(scope="module")
def client(monkeypatch_module=None):
    import uvicorn
    captured = {}

    def fake_run(app, **_):
        captured["app"] = app

    # Patch at module level
    orig = uvicorn.run
    uvicorn.run = fake_run
    try:
        run_web(host="127.0.0.1", port=0, db_path=":memory:")
    finally:
        uvicorn.run = orig

    app = captured.get("app")
    assert app is not None, "FastAPI app was not captured"
    return TestClient(app, base_url="http://localhost:7860")


# ── security headers ────────────────────────────────────────────────────────

def test_security_headers_present(client):
    r = client.get("/api/version")
    assert r.status_code == 200
    h = r.headers
    assert "content-security-policy" in {k.lower() for k in h}
    assert h.get("x-frame-options") == "DENY"
    assert h.get("x-content-type-options") == "nosniff"
    assert h.get("referrer-policy") == "no-referrer"
    assert "permissions-policy" in {k.lower() for k in h}


def test_csp_blocks_inline_script_sources(client):
    r = client.get("/api/version")
    csp = r.headers["content-security-policy"]
    # default-src self, no wildcards
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp


# ── CORS ─────────────────────────────────────────────────────────────────────

def test_cors_allows_listed_origin(client):
    r = client.options(
        "/api/version",
        headers={"Origin": "http://localhost:7860",
                 "Access-Control-Request-Method": "GET"},
    )
    assert r.headers.get("access-control-allow-origin") == "http://localhost:7860"


def test_cors_rejects_other_origins(client):
    r = client.options(
        "/api/version",
        headers={"Origin": "https://evil.example.com",
                 "Access-Control-Request-Method": "GET"},
    )
    # Either no ACL header (rejected) OR not the evil origin
    assert r.headers.get("access-control-allow-origin") != "https://evil.example.com"


# ── rate limiting ────────────────────────────────────────────────────────────

def test_rate_limit_eventually_triggers(client):
    """The global default limit (5/minute) must fire on /api/version."""
    try:
        import slowapi  # noqa: F401
    except ImportError:
        pytest.skip("slowapi not installed")
    saw_429 = False
    codes = []
    for _ in range(20):
        r = client.get("/api/version")
        codes.append(r.status_code)
        if r.status_code == 429:
            saw_429 = True
            break
    assert saw_429, f"expected a 429 within 20 calls, got: {codes}"


def test_limiter_is_wired_up(client):
    """Verify that the FastAPI app has slowapi installed and the state.limiter exists."""
    try:
        import slowapi  # noqa: F401
    except ImportError:
        pytest.skip("slowapi not installed")
    app = client.app
    assert hasattr(app.state, "limiter"), "limiter not attached to app.state"
