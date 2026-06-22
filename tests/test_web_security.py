"""Web hardening — CORS, security headers, rate limits, WebSocket origin check."""
import pytest

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


def test_godot_export_path_allows_same_origin_framing(client):
    # The World tab's <iframe src="/static/godot/index.html?run_id=..."> is
    # same-origin, so it needs an exception from the otherwise-blanket
    # frame-ancestors 'none' / X-Frame-Options: DENY -- but only 'self', never
    # a wildcard or third-party origin.
    r = client.get("/static/godot/index.html")
    csp = r.headers["content-security-policy"]
    assert "frame-ancestors 'self'" in csp
    assert "frame-ancestors 'none'" not in csp
    assert r.headers.get("x-frame-options") == "SAMEORIGIN"


def test_godot_export_path_allows_its_inline_bootstrap_script(client):
    # Godot's HTML5 export template bakes engine-bootstrap config into a
    # static inline <script> with no way to carry our per-request nonce.
    # Per the CSP spec, 'unsafe-inline' is ignored outright if a nonce is
    # ALSO present in script-src -- so this path's script-src must have no
    # nonce token at all, not just an added 'unsafe-inline'.
    r = client.get("/static/godot/index.html")
    csp = r.headers["content-security-policy"]
    script_src = csp.split("script-src", 1)[1].split(";", 1)[0]
    assert "'unsafe-inline'" in script_src
    assert "nonce-" not in script_src


def test_godot_export_path_allows_wasm_instantiation(client):
    # Godot's Emscripten WASM loader needs 'wasm-unsafe-eval' to call
    # WebAssembly.instantiateStreaming() -- the narrow, WASM-only CSP token.
    r = client.get("/static/godot/index.html")
    csp = r.headers["content-security-policy"]
    script_src = csp.split("script-src", 1)[1].split(";", 1)[0]
    assert "'wasm-unsafe-eval'" in script_src


def test_godot_export_path_allows_real_eval_for_run_id_bridge(client):
    # world_renderer.gd reads its run_id query param via
    # JavaScriptBridge.eval(), which invokes the browser's real eval() --
    # distinct from 'wasm-unsafe-eval' (WASM compilation only). Scoped to
    # this one vendored export path only.
    r = client.get("/static/godot/index.html")
    csp = r.headers["content-security-policy"]
    script_src = csp.split("script-src", 1)[1].split(";", 1)[0]
    assert "'unsafe-eval'" in script_src


def test_non_godot_paths_keep_strict_nonce_only_script_src(client):
    r = client.get("/api/version")
    csp = r.headers["content-security-policy"]
    script_src = csp.split("script-src", 1)[1].split(";", 1)[0]
    assert "nonce-" in script_src
    assert "'unsafe-inline'" not in script_src
    assert "'wasm-unsafe-eval'" not in script_src
    assert "'unsafe-eval'" not in script_src


def test_non_godot_static_paths_keep_strict_framing_policy(client):
    r = client.get("/static/js/world.js")
    csp = r.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in csp
    assert r.headers.get("x-frame-options") == "DENY"


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


def test_static_arena_css(client):
    r = client.get("/static/css/arena.css")
    assert r.status_code == 200
    assert "--bg-dark" in r.text


def test_static_arena3d_js(client):
    r = client.get("/static/arena3d.js")
    assert r.status_code == 200
    assert "ThreeJSArena" in r.text


# ── static assets ────────────────────────────────────────────────────────────

def test_static_arena3d_js_returns_200(client):
    r = client.get("/static/arena3d.js")
    assert r.status_code == 200
    assert "ThreeJSArena" in r.text


# ── playground vote rate limit ───────────────────────────────────────────────

def test_playground_vote_rate_limit(client):
    """POST /api/playground/vote must respect ARENA_RL_PLAYGROUND (3/minute)."""
    try:
        import slowapi  # noqa: F401
    except ImportError:
        pytest.skip("slowapi not installed")
    body = {
        "model_a_name": "a", "model_b_name": "b",
        "voted_for": "x", "model_x": "model_a", "model_y": "model_b",
        "prompt": "hi", "response_x": "x", "response_y": "y",
    }
    saw_429 = False
    for _ in range(10):
        r = client.post("/api/playground/vote", json=body)
        if r.status_code == 429:
            saw_429 = True
            break
    assert saw_429, "expected 429 on /api/playground/vote after exceeding limit"
