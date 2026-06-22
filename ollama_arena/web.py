"""FastAPI dashboard. Requires [web] (fastapi, uvicorn). Charts require [viz]."""
# NOTE: do NOT add `from __future__ import annotations` here. With PEP 563
# active, FastAPI's `get_type_hints()` would resolve annotations against the
# MODULE globals and fail to see `Request` / `BackgroundTasks` (they're
# imported inside `run_web`'s try/except). The visible effect was every
# route's `request: Request` being misclassified as a query parameter.
import json, logging, os, sqlite3, time, uuid
from pathlib import Path

# Imported at module scope so annotation resolution in run_web() succeeds.
# These are no-cost imports; FastAPI is already required for this module.
try:
    from fastapi import (
        FastAPI, BackgroundTasks, HTTPException, Request,
        WebSocket, WebSocketDisconnect,
    )
    from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, RedirectResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware
    from starlette.middleware.base import BaseHTTPMiddleware
except ImportError:
    # Allow `import ollama_arena.web` even when [web] extras aren't installed
    # — run_web() will raise the same friendly error when actually called.
    FastAPI = BackgroundTasks = HTTPException = Request = None       # type: ignore
    WebSocket = WebSocketDisconnect = None                            # type: ignore
    HTMLResponse = JSONResponse = StreamingResponse = RedirectResponse = None  # type: ignore
    CORSMiddleware = BaseHTTPMiddleware = None                        # type: ignore

log = logging.getLogger("arena.web")

# ── Security configuration (overridable via env) ─────────────────────────────
# Default to localhost only — explicit allowlist beats `*` wildcard CORS.
_ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv(
        "ARENA_ALLOWED_ORIGINS",
        "http://localhost:7860,http://127.0.0.1:7860,"
        "http://localhost:7861,http://127.0.0.1:7861,"
        "http://localhost:8080,http://127.0.0.1:8080",
    ).split(",") if o.strip()
]
# Open CORS only if explicitly requested (e.g. ARENA_ALLOWED_ORIGINS=*).
_CORS_OPEN = _ALLOWED_ORIGINS == ["*"]
# Rate limit overrides (per-IP, per-route, per-window).
_RL_MATCH       = os.getenv("ARENA_RL_MATCH",       "2/minute")
_RL_TOURNAMENT  = os.getenv("ARENA_RL_TOURNAMENT",  "1/minute")
_RL_PLAYGROUND  = os.getenv("ARENA_RL_PLAYGROUND",  "10/minute")
_RL_SPEC_STREAM = os.getenv("ARENA_RL_SPEC_STREAM", "20/minute")
_RL_DEFAULT     = os.getenv("ARENA_RL_DEFAULT",     "120/minute")
# Ephemeral in-memory job TTL (seconds). Read at cleanup time via ARENA_JOB_TTL env.

# Role -> model overrides set via the "Providers" tab UI (/api/role-routing).
# A plain JSON file, not sim.db -- this is process-wide routing config, not
# a particular run's data, and editing it by hand is meant to work too.
# Default location; run_web(role_models_path=...) overrides it (tests use
# this to avoid touching the real ~/.config during a test run).
_DEFAULT_ROLE_MODELS_PATH = os.path.expanduser("~/.config/ollama-arena/role_models.json")


def run_web(
    host: str = "0.0.0.0",
    port: int = 7860,
    ollama_url: str = "http://localhost:11434",
    db_path: str = "arena.db",
    backend: str | None = None,
    api_key: str | None = None,
    role_models_path: str | None = None,
    secrets_key_path: str | None = None,
    secrets_store_path: str | None = None,
):
    if FastAPI is None:
        raise RuntimeError("Install: pip install 'ollama-arena[web]'")
    import uvicorn

    _role_models_path = role_models_path or _DEFAULT_ROLE_MODELS_PATH

    def _load_role_models() -> dict:
        if not os.path.exists(_role_models_path):
            return {}
        try:
            with open(_role_models_path) as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_role_models(mapping: dict) -> None:
        os.makedirs(os.path.dirname(_role_models_path), exist_ok=True)
        with open(_role_models_path, "w") as f:
            json.dump(mapping, f, indent=2)

    from .secrets_store import SecretsStore
    _secrets = SecretsStore(key_path=secrets_key_path, store_path=secrets_store_path)

    # SlowAPI rate limiting — optional but strongly recommended in prod.
    try:
        from slowapi import Limiter, _rate_limit_exceeded_handler
        from slowapi.util import get_remote_address
        from slowapi.errors import RateLimitExceeded
        _LIMITER_AVAILABLE = True
    except ImportError:
        log.warning("slowapi not installed — rate limits disabled "
                    "(install with: pip install slowapi)")
        _LIMITER_AVAILABLE = False

    from .arena import Arena
    from .tasks import list_categories, task_stats, list_languages
    from .datasets import available_datasets
    from .visualize import (
        elo_timeline_html, radar_html, heatmap_html,
        performance_chart_html, leaderboard_table_html,
    )

    arena = Arena(ollama_url=ollama_url, db_path=db_path,
                  backend=backend, api_key=api_key)
    # Ephemeral in-memory job store: survives only for this process lifetime.
    # Entries are pruned after ARENA_JOB_TTL seconds (default 1h). Server restarts
    # wipe all jobs — clients must poll /api/job/{id} promptly and must not treat
    # job_id as durable storage. Optional SQLite persistence is a future improvement.
    jobs: dict[str, dict] = {}

    def _cleanup_jobs() -> None:
        ttl = float(os.getenv("ARENA_JOB_TTL", "3600"))
        if ttl <= 0:
            return
        cutoff = time.time() - ttl
        for jid in [k for k, v in jobs.items() if v.get("created_at", 0) < cutoff]:
            del jobs[jid]

    def _new_job_id() -> str:
        _cleanup_jobs()
        return str(uuid.uuid4())

    def _body_num(body: dict, key: str, default, cast=int):
        """Pull a numeric field out of a request body, raising a clean 400
        instead of letting int()/float() throw an unhandled ValueError that
        FastAPI would otherwise turn into a raw 500 on plausible bad input
        (e.g. a client sending {"n": "abc"})."""
        val = body.get(key, default)
        try:
            return cast(val)
        except (TypeError, ValueError):
            raise HTTPException(400, f"{key!r} must be a {cast.__name__}, got {val!r}")

    class ConnectionManager:
        def __init__(self) -> None:
            self.active_connections: list[WebSocket] = []

        async def connect(self, websocket: WebSocket) -> None:
            await websocket.accept()
            self.active_connections.append(websocket)
            log.info(f"WebSocket connected. Total active: {len(self.active_connections)}")

        def disconnect(self, websocket: WebSocket) -> None:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
                log.info(f"WebSocket disconnected. Total active: {len(self.active_connections)}")

        async def broadcast(self, message: dict) -> None:
            import asyncio
            dead_connections: list[WebSocket] = []
            for connection in self.active_connections:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    log.warning(f"Broadcast failed, marking connection as dead: {e}")
                    dead_connections.append(connection)
            
            for dead in dead_connections:
                self.disconnect(dead)

    manager = ConnectionManager()

    from . import __version__
    app = FastAPI(title="Ollama Arena", version=__version__)
    HERE = Path(__file__).parent.parent / "templates"

    # ── Rate limiting ────────────────────────────────────────────────────────
    if _LIMITER_AVAILABLE:
        from slowapi.middleware import SlowAPIMiddleware
        limiter = Limiter(key_func=get_remote_address, default_limits=[_RL_DEFAULT])
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        app.add_middleware(SlowAPIMiddleware)
    else:
        # No-op decorator so the codepath stays uniform
        class _NoLimiter:
            def limit(self, *_a, **_kw):
                def _decorator(fn): return fn
                return _decorator
        limiter = _NoLimiter()

    # ── CORS ─────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_ALLOWED_ORIGINS if not _CORS_OPEN else ["*"],
        allow_credentials=not _CORS_OPEN,    # credentials cannot pair with "*"
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
        max_age=600,
    )

    # ── Security headers middleware ──────────────────────────────────────────
    class SecurityHeadersMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            nonce = uuid.uuid4().hex
            request.state.csp_nonce = nonce
            response = await call_next(request)
            # The Godot Web export is embedded same-origin via the World
            # tab's <iframe src="/static/godot/index.html?...">. A blanket
            # frame-ancestors 'none' (the right default everywhere else, to
            # block third-party clickjacking) would block that legitimate
            # same-origin embedding too, so only this one path tree relaxes
            # to 'self' — never to a wildcard or external origin.
            is_godot_export = request.url.path.startswith("/static/godot/")
            frame_ancestors = "'self'" if is_godot_export else "'none'"
            # Godot's HTML5 export template bakes its engine-bootstrap
            # config (file sizes, executable name) into a static inline
            # <script> in index.html, generated by Godot's own build
            # tooling -- it has no way to carry our per-request nonce. Per
            # the CSP spec, 'unsafe-inline' is ignored outright whenever a
            # nonce/hash is ALSO present in script-src, so this path must
            # drop the nonce token entirely (not just add 'unsafe-inline')
            # for the relaxation to take effect. This vendored,
            # auto-generated bundle (not user input, not
            # attacker-influenced) is the one exception; every other path
            # keeps the strict nonce-only script-src. Godot's Emscripten
            # WASM loader also needs 'wasm-unsafe-eval' to call
            # WebAssembly.instantiateStreaming(). Separately, world_renderer.gd
            # reads its run_id query param via JavaScriptBridge.eval(), which
            # invokes the browser's real eval() (not WASM compilation) -- this
            # requires the broader 'unsafe-eval' token too. Both tokens are
            # still scoped to this one vendored, non-user-content export path;
            # every other path keeps the strict nonce-only script-src with
            # neither token.
            script_src_value = (
                "'self' 'unsafe-inline' 'wasm-unsafe-eval' 'unsafe-eval'" if is_godot_export
                else f"'self' 'nonce-{nonce}'"
            )
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                f"script-src {script_src_value} "
                "  https://cdn.plot.ly https://cdnjs.cloudflare.com "
                "  https://cdn.jsdelivr.net; "
                # No nonce here: dynamically-loaded chart/leaderboard HTML
                # fragments (injected via innerHTML in match.js) carry inline
                # style="..." attributes that the server already HTML-escapes
                # for the values they embed, so 'unsafe-inline' is an
                # acceptable tradeoff for style-src specifically — script-src
                # above keeps the strict nonce requirement.
                "style-src 'self' 'unsafe-inline' "
                "  https://cdnjs.cloudflare.com https://fonts.googleapis.com "
                "  https://unpkg.com; "
                "font-src 'self' https://fonts.gstatic.com data:; "
                "img-src 'self' data: blob: https:; "
                "connect-src 'self' ws: wss:; "
                f"frame-ancestors {frame_ancestors}; "
                "base-uri 'self'; "
                "object-src 'none'; "
                "form-action 'self';"
            )
            response.headers["X-Frame-Options"]        = "SAMEORIGIN" if is_godot_export else "DENY"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"]        = "no-referrer"
            response.headers["Permissions-Policy"]     = (
                "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
                "microphone=(), payment=(), usb=()"
            )
            response.headers["X-XSS-Protection"]       = "0"
            if request.url.path.startswith("/static/"):
                # FastAPI's StaticFiles sends no Cache-Control by default, so
                # browsers fall back to heuristic caching and can keep serving
                # a stale script/style indefinitely after a deploy. Force
                # revalidation on every load (the ETag/Last-Modified pair
                # StaticFiles already sets makes that revalidation cheap).
                response.headers["Cache-Control"] = "no-cache"
            return response
    app.add_middleware(SecurityHeadersMiddleware)

    STATIC_ROOT = Path(__file__).parent.parent / "static"
    if STATIC_ROOT.is_dir():
        from fastapi.staticfiles import StaticFiles
        app.mount("/static", StaticFiles(directory=str(STATIC_ROOT)), name="static")

    # Cache-busting query param for local static assets, set once per process
    # start: without it, browsers that already cached an old script/style can
    # keep serving it indefinitely after a deploy (no-cache still costs a
    # revalidation round-trip per load; this avoids that entirely on top of it).
    ASSET_VERSION = uuid.uuid4().hex[:8]

    from jinja2 import Environment, FileSystemLoader, select_autoescape
    jinja = Environment(
        loader=FileSystemLoader(str(HERE)),
        autoescape=select_autoescape(["html"]),
    )

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        tmpl = jinja.get_template("index.html")
        return HTMLResponse(tmpl.render(csp_nonce=request.state.csp_nonce, asset_version=ASSET_VERSION))

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        # ── Origin validation (CSRF-style) — close before accepting ───────
        origin = websocket.headers.get("origin")
        if not _CORS_OPEN and origin and origin not in _ALLOWED_ORIGINS:
            log.warning(f"WebSocket rejected: bad Origin {origin!r}")
            # Close code 1008 = "policy violation"
            await websocket.close(code=1008, reason="Origin not allowed")
            return
        await manager.connect(websocket)
        try:
            while True:
                data = await websocket.receive_text()
        except WebSocketDisconnect:
            log.info("WebSocket client disconnected gracefully.")
            manager.disconnect(websocket)
        except Exception as e:
            log.error(f"WebSocket error: {e}")
            manager.disconnect(websocket)

    # Small leaderboard/history cache (1s TTL) — high-traffic endpoints
    _lb_cache = {"t": 0.0, "data": None}
    _hist_cache: dict = {}

    @app.get("/api/leaderboard")
    def api_leaderboard():
        now = time.time()
        if _lb_cache["data"] and now - _lb_cache["t"] < 1.0:
            return _lb_cache["data"]
        data = arena.leaderboard()
        _lb_cache["t"] = now; _lb_cache["data"] = data
        return data

    @app.get("/api/anti-leaderboard")
    def api_anti_leaderboard():
        return arena.elo.anti_leaderboard()

    @app.get("/api/history")
    def api_history(limit: int = 50):
        now = time.time()
        c = _hist_cache.get(limit)
        if c and now - c["t"] < 1.0:
            return c["data"]
        data = arena.match_history(limit=limit)
        _hist_cache[limit] = {"t": now, "data": data}
        return data

    @app.get("/api/history/search")
    def api_history_search(q: str = "", limit: int = 50):
        """Full-text search over match history (model names, category)."""
        if not q.strip():
            return arena.match_history(limit=limit)
        q_lower = q.lower()
        all_matches = arena.match_history(limit=500)
        results = [
            m for m in all_matches
            if q_lower in m.get("model_a", "").lower()
            or q_lower in m.get("model_b", "").lower()
            or q_lower in m.get("category", "").lower()
        ]
        return results[:limit]

    @app.get("/api/stats", summary="Arena global statistics",
             description="Aggregate stats: total matches, total tasks, active models, "
                         "avg ELO, avg TPS, and recency metrics.")
    def api_arena_stats():
        return arena.elo.arena_stats()

    @app.get("/api/compare/{model_a:path}", summary="Head-to-head model comparison",
             description="Win/draw/loss breakdown and category-level ELO comparison "
                         "between two models. Use ?b= to specify the second model. "
                         "Example: /api/compare/llama3?b=phi3")
    def api_compare(model_a: str, b: str = ""):
        if not b:
            raise HTTPException(status_code=400, detail="Missing ?b= parameter")
        return arena.elo.head_to_head(model_a, b)

    @app.get("/api/leaderboard/{category}", summary="Category-specific ELO leaderboard",
             description="Returns the ELO leaderboard filtered to one category "
                         "(e.g. 'code', 'math', 'reasoning'). Models with no matches "
                         "in that category are excluded.")
    def api_category_leaderboard(category: str):
        return arena.elo.category_leaderboard(category)

    @app.get("/api/models/{model:path}/elo-by-category",
             summary="Per-category ELO breakdown for a model",
             description="Returns all category sub-ratings for the given model, "
                         "sorted by number of matches descending.")
    def api_model_category_elos(model: str):
        return arena.elo.model_category_elos(model)

    @app.get("/api/export", summary="Export full arena data",
             description="Download a full arena snapshot. "
                         "Use ?fmt=json (default) for a structured JSON bundle "
                         "(stats + leaderboard + full match history + benchmarks) "
                         "or ?fmt=csv for a flat CSV of every match.")
    def api_export(fmt: str = "json"):
        """Export full arena data. fmt=json (default) or fmt=csv."""
        import csv
        import io
        import time as _time

        if fmt == "csv":
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow([
                "id", "model_a", "model_b", "category",
                "score_a", "score_b", "elo_a_before", "elo_b_before",
                "elo_a_after", "elo_b_after", "ts",
            ])
            for m in arena.match_history(limit=10000):
                writer.writerow([
                    m.get("id"), m.get("model_a"), m.get("model_b"),
                    m.get("category"), m.get("score_a"), m.get("score_b"),
                    m.get("elo_a_before"), m.get("elo_b_before"),
                    m.get("elo_a_after"), m.get("elo_b_after"), m.get("ts"),
                ])
            buf.seek(0)
            from fastapi.responses import Response
            return Response(
                content=buf.getvalue(),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=arena_matches.csv"},
            )

        # JSON export — include everything useful
        payload = {
            "exported_at": _time.time(),
            "stats": arena.elo.arena_stats(),
            "leaderboard": arena.leaderboard(),
            "match_history": arena.match_history(limit=10000),
            "benchmark_history": arena.elo.benchmark_history(limit=200),
        }
        import json as _json
        from fastapi.responses import Response
        return Response(
            content=_json.dumps(payload, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=arena_export.json"},
        )

    @app.get("/api/models", summary="List available models",
             description="Returns all models reported by the active backend, "
                         "enriched with auto-detected capability flags "
                         "(vision, tools, ctx_length) where available.")
    def api_models():
        models = arena.client.list_models()
        # Enrich with capabilities. A cache miss makes one HTTP call per
        # model (up to ~10s each) — detect_all() runs those in parallel
        # threads instead of the previous serial loop, which could stall
        # this endpoint for 10s x N models on a cold cache.
        try:
            from .model_caps import detect_all
            names = [m if isinstance(m, str) else m.get("name", "") for m in models]
            caps_by_name = detect_all([n for n in names if n], ollama_url)
            for m, name in zip(models, names):
                if name and isinstance(m, dict):
                    m["caps"] = caps_by_name.get(name, {})
        except Exception:
            pass
        return models

    @app.get("/api/providers", summary="List backend providers/presets",
             description="Every OpenAICompatBackend preset plus local Ollama, "
                         "classified local/free/paid, with only a boolean "
                         "key-configured flag -- never the key value itself.")
    def api_providers():
        from .backends.openai_compat import OpenAICompatBackend
        local_presets = {"vllm", "lmstudio", "llamacpp"}
        free_capable = {"openrouter", "opencode"}
        out = [{
            "name": "ollama", "base_url": ollama_url, "env_key": None,
            "key_configured": True, "kind": "local",
        }]
        for name, url in OpenAICompatBackend.PRESETS.items():
            env_key = OpenAICompatBackend._ENV_KEY_MAP.get(name, "OPENAI_API_KEY")
            out.append({
                "name": name, "base_url": url, "env_key": env_key,
                "key_configured": bool(os.environ.get(env_key)) or _secrets.has_key(name),
                "kind": "local" if name in local_presets
                        else "free" if name in free_capable else "paid",
            })
        return JSONResponse(sorted(out, key=lambda p: (p["kind"], p["name"])))

    @app.post("/api/providers/{name}/key", summary="Store an API key for a provider",
              description="Body: {api_key}. Encrypted at rest (secrets_store.py), "
                          "never echoed back in this or any other response. "
                          "Local runtimes (ollama/vllm/lmstudio/llamacpp) don't take a key.")
    def api_provider_set_key(name: str, body: dict):
        from .backends.openai_compat import OpenAICompatBackend
        local_presets = {"vllm", "lmstudio", "llamacpp"}
        if name == "ollama" or name in local_presets:
            raise HTTPException(400, f"{name!r} is a local runtime and doesn't take an API key")
        if name not in OpenAICompatBackend.PRESETS:
            raise HTTPException(400, f"unknown provider {name!r}")
        value = (body.get("api_key") or "").strip()
        if not value:
            raise HTTPException(400, "api_key must be a non-empty string")
        try:
            _secrets.set_key(name, value)
        except Exception as e:
            raise HTTPException(500, f"could not store key: {e}")
        return JSONResponse({"key_configured": True})

    @app.delete("/api/providers/{name}/key", summary="Clear a stored API key")
    def api_provider_clear_key(name: str):
        _secrets.clear_key(name)
        return JSONResponse({"key_configured": False})

    @app.get("/api/model-registry", summary="Free-model registry",
             description="Provider-agnostic catalog of known free models "
                         "(model_registry.py), with tool/JSON-mode/context "
                         "badges -- the same table model_router.py routes against.")
    def api_model_registry():
        from .model_registry import load_registry
        return JSONResponse([
            {
                "id": e.id, "provider": e.provider, "source": e.source,
                "free": e.free, "supports_tools": e.supports_tools,
                "supports_json": e.supports_json, "max_context": e.max_context,
                "cost_tier": e.cost_tier, "role_tags": list(e.role_tags),
                "fallback_chain": list(e.fallback_chain),
            }
            for e in load_registry()
        ])

    @app.get("/api/role-routing", summary="Get role -> model routing config")
    def api_role_routing_get():
        from .model_registry import SIM_ROLES
        return JSONResponse({"roles": list(SIM_ROLES), "role_models": _load_role_models()})

    @app.post("/api/role-routing", summary="Set or clear one role's model",
              description="Body: {role, model}. Omitting model clears that "
                          "role back to default (no router override).")
    def api_role_routing_set(body: dict):
        from .model_registry import SIM_ROLES
        role = body.get("role")
        if role not in SIM_ROLES:
            raise HTTPException(400, f"unknown role {role!r}, must be one of {list(SIM_ROLES)}")
        mapping = _load_role_models()
        model = body.get("model")
        if model:
            mapping[role] = model
        else:
            mapping.pop(role, None)
        _save_role_models(mapping)
        return JSONResponse({"role_models": mapping})

    @app.get("/api/models/{model:path}/caps",
             summary="Model capability detection",
             description="Auto-detects model capabilities via Ollama /api/show. "
                         "Results are cached per process. Fields: vision (bool), "
                         "tools (bool), ctx_length (int), families (list), param_size (str).")
    def api_model_caps(model: str):
        from .model_caps import get as get_caps
        return get_caps(model, ollama_url)

    @app.get("/api/categories", summary="Available task categories and languages",
             description="Returns the list of supported task categories, "
                         "programming languages, and aggregate task statistics.")
    def api_categories():
        return {"categories": list_categories(),
                "languages": list_languages(),
                "stats": task_stats()}

    @app.get("/api/perf", summary="Model performance statistics",
             description="Latency, TPS, and throughput percentiles aggregated "
                         "from all completed matches in the current session.")
    def api_perf():
        return arena.performance_stats()

    @app.get("/api/datasets", summary="Available benchmark datasets",
             description="Returns metadata for all built-in benchmark datasets "
                         "including HuggingFace sources and custom task sets.")
    def api_datasets():
        return available_datasets()

    @app.get("/api/version", summary="Arena version",
             description="Returns the installed ollama-arena package version.")
    def api_version():
        from . import __version__
        return {"version": __version__}

    # ── System telemetry (cheap, polled every 2s by dashboard) ────────────────
    _sys_cache = {"t": 0.0, "data": None}

    @app.get("/api/system")
    def api_system():
        import time as _t
        now = _t.time()
        # Cache for 1s to avoid hammering psutil
        if _sys_cache["data"] and now - _sys_cache["t"] < 1.0:
            return _sys_cache["data"]
        try:
            import psutil
            vm = psutil.virtual_memory()
            data = {
                "cpu_pct":  psutil.cpu_percent(interval=None),
                "ram_pct":  vm.percent,
                "ram_used_gb": round(vm.used / 1024**3, 1),
                "ram_total_gb": round(vm.total / 1024**3, 1),
                "ts": now,
            }
        except Exception:
            data = {"cpu_pct": 0, "ram_pct": 0, "ram_used_gb": 0, "ram_total_gb": 0, "ts": now}
        # GPU memory via Ollama /api/ps
        try:
            import requests as _rq
            if getattr(arena.client, "name", "") == "ollama" and hasattr(arena.client, "base"):
                r = _rq.get(f"{arena.client.base}/api/ps", timeout=1.5)
                if r.ok:
                    models = r.json().get("models", [])
                    data["loaded_models"] = [
                        {"name": m.get("name", ""), "size_gb": round(m.get("size", 0) / 1024**3, 2)}
                        for m in models
                    ]
                    data["vram_used_gb"] = round(
                        sum(m.get("size", 0) for m in models) / 1024**3, 1
                    )
                else:
                    data["loaded_models"] = []
                    data["vram_used_gb"] = 0
            else:
                data["loaded_models"] = []
                data["vram_used_gb"] = 0
        except Exception:
            data["loaded_models"] = []
            data["vram_used_gb"] = 0
        _sys_cache["t"] = now
        _sys_cache["data"] = data
        return data

    @app.get("/api/task/{task_id}")
    def api_task_history(task_id: str):
        runs = arena.elo.task_history(task_id)
        for r in runs:
            for k in ("tool_call_a", "tool_call_b"):
                raw = r.get(k)
                if raw and isinstance(raw, str):
                    try:
                        r[k] = json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        pass
        return {"runs": runs}

    @app.post("/api/retry_task/{task_id}")
    @limiter.limit("8/minute")
    def api_retry_task(task_id: str, request: Request):
        """Re-run a single task using the same model_a/model_b/instruction
        captured in the latest task_detail row. Recomputes ELO incrementally."""
        try:
            return arena.retry_task(task_id)
        except ValueError as e:
            raise HTTPException(404, str(e))
        except Exception as e:
            log.exception(f"retry_task({task_id}) failed")
            raise HTTPException(500, str(e))

    @app.get("/api/report/{model}")
    def api_report(model: str):
        return arena.elo.category_stats(model)

    @app.get("/api/export_match/{match_id}")
    def api_export_match(match_id: int):
        from .visualize import export_match_report
        tasks = arena.elo.tasks_for_match(match_id)
        history = arena.elo.match_history(limit=1000)
        info = next((m for m in history if m["id"] == match_id), None)
        if not info:
            raise HTTPException(404, f"Match {match_id} not found")
        path = export_match_report(match_id, info, tasks)
        return {"path": path, "filename": Path(path).name}

    @app.get("/api/export_royale/{royale_id}")
    def api_export_royale(royale_id: int):
        from .visualize import export_royale_report
        entries = arena.elo.royale_entries(royale_id)
        if not entries:
            raise HTTPException(404, f"Royale {royale_id} not found")
        # We need model names and category for royale report
        # Let's get them from royale_log
        try:
            with sqlite3.connect(db_path) as cx:
                row = cx.execute("SELECT category FROM royale_log WHERE id=?", (royale_id,)).fetchone()
                category = row[0] if row else "unknown"
        except: category = "unknown"
        
        models = sorted(list(set(e["model"] for e in entries)))
        path = export_royale_report(royale_id, category, models, entries)
        return {"path": path, "filename": Path(path).name}

    # Charts (HTML fragments rendered via Plotly)
    @app.get("/charts/elo")
    def chart_elo():
        try:
            return HTMLResponse(elo_timeline_html(arena.match_history(limit=1000)))
        except RuntimeError as e:
            return HTMLResponse(f"<div style='color:#8b949e;padding:20px'>{e}</div>")

    @app.get("/charts/radar")
    def chart_radar():
        try:
            return HTMLResponse(radar_html(arena.match_history(limit=1000), list_categories()))
        except RuntimeError as e:
            return HTMLResponse(f"<div style='color:#8b949e;padding:20px'>{e}</div>")

    @app.get("/charts/heatmap")
    def chart_heatmap():
        try:
            return HTMLResponse(heatmap_html(arena.match_history(limit=1000)))
        except RuntimeError as e:
            return HTMLResponse(f"<div style='color:#8b949e;padding:20px'>{e}</div>")

    @app.get("/charts/perf")
    def chart_perf():
        try:
            return HTMLResponse(performance_chart_html(arena.performance_stats()))
        except RuntimeError as e:
            return HTMLResponse(f"<div style='color:#8b949e;padding:20px'>{e}</div>")

    _chart_cache: dict = {}
    _CHART_TTL = 5.0

    def _cached_chart(key: str, fn):
        now = time.time()
        c = _chart_cache.get(key)
        if c and now - c["t"] < _CHART_TTL:
            return c["html"]
        try:
            h = fn()
        except RuntimeError as e:
            h = f"<div style='color:#8b949e;padding:20px'>{e}</div>"
        _chart_cache[key] = {"t": now, "html": h}
        return h

    @app.get("/charts/leaderboard")
    def chart_lb():
        return HTMLResponse(_cached_chart("lb", lambda: leaderboard_table_html(arena.leaderboard())))

    # ── Memory-Adaptive Pipeline Tournament — preview the strategy ──────
    @app.post("/api/strategy")
    @limiter.limit("30/minute")
    def api_strategy(request: Request, body: dict):
        """Return which execution mode the scheduler would pick for this pair.

        Lets the UI render a badge ("⚡ CONCURRENT", "↔️ HOT SWAP",
        "🔁 PIPELINE", "⛔ INSUFFICIENT") before the user hits Engage Combat.
        """
        ma = str(body.get("model_a") or "").strip()
        mb = str(body.get("model_b") or "").strip()
        if not ma or not mb:
            raise HTTPException(400, "model_a and model_b required")
        d = arena.scheduler.choose(ma, mb)
        return {
            **d.to_dict(),
            "total_ram_gb":  round(arena.scheduler.total_ram_gb(), 2),
            "usable_ram_gb": round(arena.scheduler.usable_ram_gb(), 2),
            "loaded_gb":     round(arena.scheduler.loaded_models_gb(), 2),
        }

    # Run a match
    @app.post("/api/match")
    @limiter.limit(_RL_MATCH)
    def api_run_match(request: Request, body: dict, tasks: BackgroundTasks):
        ma = body.get("model_a", ""); mb = body.get("model_b", "")
        cat = body.get("category", "coding"); n = _body_num(body, "n", 5)
        concurrency = _body_num(body, "concurrency", 1)
        if not ma or not mb:
            raise HTTPException(400, "model_a and model_b required")
        jid = _new_job_id()
        jobs[jid] = {"status": "running", "log": [], "model_a": ma, "model_b": mb,
                     "created_at": time.time()}

        import asyncio

        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            def on_task(tid, sa, sb, outcome, instruction="", resp_a="", resp_b="", expected=""):
                event = {
                    "type": "task_done",
                    "job_id": jid,
                    "task_id": tid, "score_a": sa, "score_b": sb, "outcome": outcome,
                    "instruction": instruction[:200] if instruction else "",
                    "resp_a": resp_a[:300] if resp_a else "",
                    "resp_b": resp_b[:300] if resp_b else "",
                }
                jobs[jid]["log"].append(event)
                loop.run_until_complete(manager.broadcast(event))

            def on_phase(event):
                ev = {"type": "strategy_event", "job_id": jid, **event}
                jobs[jid]["log"].append(ev)
                loop.run_until_complete(manager.broadcast(ev))

            arena._on_task_done = on_task
            arena._on_phase     = on_phase
            try:
                r = arena.run_match(ma, mb, category=cat, n=n, concurrency=concurrency)
                jobs[jid]["status"] = "done"
                result_data = {
                    "a_wins": r.a_wins, "b_wins": r.b_wins, "draws": r.draws,
                    "elo_a_after": r.elo_a_after, "elo_b_after": r.elo_b_after,
                    "duration_s": r.duration_s,
                    "strategy": r.strategy,
                    "strategy_reason": r.strategy_reason,
                }
                jobs[jid]["result"] = result_data
                loop.run_until_complete(manager.broadcast({
                    "type": "job_done",
                    "job_id": jid,
                    "result": result_data
                }))
            except Exception as e:
                jobs[jid]["status"] = "error"
                jobs[jid]["error"] = str(e)
                loop.run_until_complete(manager.broadcast({
                    "type": "job_error",
                    "job_id": jid,
                    "error": str(e)
                }))

        tasks.add_task(_run)
        return {"job_id": jid}

    @app.get("/api/job/{job_id}")
    def api_job(job_id: str):
        _cleanup_jobs()
        return jobs.get(job_id, {"status": "not_found"})

    @app.post("/api/tournament")
    @limiter.limit(_RL_TOURNAMENT)
    def api_run_tournament(request: Request, body: dict, tasks: BackgroundTasks):
        models = body.get("models", [])
        cat = body.get("category", "coding")
        n = _body_num(body, "n", 3)
        concurrency = _body_num(body, "concurrency", 1)

        if not isinstance(models, list) or len(models) < 2:
            raise HTTPException(400, "At least 2 models required for a tournament")

        jid = _new_job_id()
        jobs[jid] = {"status": "running", "log": [], "type": "tournament",
                     "models": models, "created_at": time.time()}

        import asyncio
        from itertools import combinations

        def _run_tournament():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            pairs = list(combinations(models, 2))
            total_matches = len(pairs)
            
            loop.run_until_complete(manager.broadcast({
                "type": "tournament_start",
                "job_id": jid,
                "total_matches": total_matches,
                "pairs": pairs
            }))

            for i, (ma, mb) in enumerate(pairs, 1):
                loop.run_until_complete(manager.broadcast({
                    "type": "tournament_match_start",
                    "job_id": jid,
                    "match_num": i,
                    "total_matches": total_matches,
                    "model_a": ma,
                    "model_b": mb
                }))
                
                # Use a custom task callback for the tournament to avoid spamming the UI with individual task events,
                # or we can just let it be quiet and only announce match results.
                arena._on_task_done = None 
                
                try:
                    r = arena.run_match(ma, mb, category=cat, n=n, concurrency=concurrency)
                    loop.run_until_complete(manager.broadcast({
                        "type": "tournament_match_done",
                        "job_id": jid,
                        "match_num": i,
                        "model_a": ma,
                        "model_b": mb,
                        "a_wins": r.a_wins,
                        "b_wins": r.b_wins,
                        "draws": r.draws
                    }))
                except Exception as e:
                    log.error(f"Tournament match failed between {ma} and {mb}: {e}")
                    # Broadcast error to avoid UI hanging forever
                    loop.run_until_complete(manager.broadcast({
                        "type": "tournament_match_error",
                        "job_id": jid,
                        "match_num": i,
                        "model_a": ma,
                        "model_b": mb,
                        "error": str(e)
                    }))
                    # Throttle retries to prevent rapid crash looping
                    loop.run_until_complete(asyncio.sleep(2.0))

            jobs[jid]["status"] = "done"
            loop.run_until_complete(manager.broadcast({
                "type": "tournament_done",
                "job_id": jid,
                "leaderboard": arena.leaderboard()
            }))

        tasks.add_task(_run_tournament)
        return {"job_id": jid}

    @app.post("/api/royale")
    @limiter.limit(_RL_MATCH)
    def api_run_royale(request: Request, body: dict, tasks: BackgroundTasks):
        models = body.get("models", [])
        cat = body.get("category", "coding")
        n = _body_num(body, "n", 5)
        if not isinstance(models, list) or len(models) < 3:
            raise HTTPException(400, "Battle Royale requires at least 3 models")

        jid = _new_job_id()
        jobs[jid] = {"status": "running", "log": [], "type": "royale",
                     "models": models, "created_at": time.time()}

        import asyncio

        def _run_royale():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            def on_task(tid, sa, sb, outcome, instruction="", resp_a="", resp_b="", expected=""):
                # In royale, we just show round progress for now
                event = {"type": "royale_task_done", "job_id": jid, "task_id": tid}
                jobs[jid]["log"].append(event)
                loop.run_until_complete(manager.broadcast(event))

            arena._on_task_done = on_task
            try:
                r = arena.run_royale(models, category=cat, n=n)
                jobs[jid]["status"] = "done"
                result_data = {
                    "winner": r.winner,
                    "rankings": r.rankings,
                    "duration_s": r.duration_s,
                    "royale_id": r.royale_id,
                    "strategy": r.strategy
                }
                jobs[jid]["result"] = result_data
                loop.run_until_complete(manager.broadcast({
                    "type": "royale_done",
                    "job_id": jid,
                    "result": result_data
                }))
            except Exception as e:
                log.exception("Royale failed")
                jobs[jid]["status"] = "error"
                jobs[jid]["error"] = str(e)
                loop.run_until_complete(manager.broadcast({
                    "type": "job_error",
                    "job_id": jid,
                    "error": str(e)
                }))

        tasks.add_task(_run_royale)
        return {"job_id": jid}

    # Playground A/B endpoints
    @app.post("/api/playground/generate_single")
    @limiter.limit(_RL_PLAYGROUND)
    def api_playground_generate_single(request: Request, body: dict):
        model = body.get("model", "")
        prompt = body.get("prompt", "")
        enable_tools = body.get("enable_tools", False)
        if not model or not prompt:
            raise HTTPException(400, "model and prompt required")

        if enable_tools and hasattr(arena, 'mcp') and arena.mcp:
            from .agent_loop import run_agent_sync
            res = run_agent_sync(arena.client, model, prompt, arena.mcp, max_steps=8)
            arena._log_perf(model, res)
            trace = getattr(res, 'agent_trace', None) or []
            return {
                "model": model,
                "response": res.text if res.ok else f"[ERROR: {res.error}]",
                "tps": res.tps,
                "latency_s": res.latency_s,
                "agent_trace": trace,
                "finish_reason": getattr(res, 'finish_reason', 'stop'),
            }

        res = arena.client.generate(model, prompt)
        arena._log_perf(model, res)
        return {
            "model": model,
            "response": res.text if res.ok else f"[ERROR: {res.error}]",
            "tps": res.tps,
            "latency_s": res.latency_s,
        }

    @app.post("/api/playground/generate")
    @limiter.limit(_RL_PLAYGROUND)
    def api_playground_generate(request: Request, body: dict):
        model_a = body.get("model_a", "")
        model_b = body.get("model_b", "")
        prompt = body.get("prompt", "")
        if not model_a or not model_b or not prompt:
            raise HTTPException(400, "model_a, model_b, and prompt required")

        res_a = arena.client.generate(model_a, prompt)
        res_b = arena.client.generate(model_b, prompt)

        arena._log_perf(model_a, res_a)
        arena._log_perf(model_b, res_b)

        import random
        swap = random.choice([True, False])
        if swap:
            resp_x, resp_y = res_b, res_a
            label_x, label_y = "model_b", "model_a"
        else:
            resp_x, resp_y = res_a, res_b
            label_x, label_y = "model_a", "model_b"

        return {
            "response_x": resp_x.text if resp_x.ok else f"[ERROR: {resp_x.error}]",
            "response_y": resp_y.text if resp_y.ok else f"[ERROR: {resp_y.error}]",
            "model_x": label_x,
            "model_y": label_y,
            "tps_x": resp_x.tps,
            "tps_y": resp_y.tps,
            "latency_x": resp_x.latency_s,
            "latency_y": resp_y.latency_s,
        }

    @app.post("/api/playground/vote")
    @limiter.limit(_RL_PLAYGROUND)
    def api_playground_vote(request: Request, body: dict):
        model_a_name = body.get("model_a_name", "")
        model_b_name = body.get("model_b_name", "")
        voted_for = body.get("voted_for", "")  # "x", "y", "draw"
        model_x_name = body.get("model_x", "")  # Frontend passes "model_x", not "model_x_name"
        model_y_name = body.get("model_y", "")
        
        # Fallbacks if frontend named them differently
        if not model_x_name: model_x_name = body.get("model_x_name", "")
        if not model_y_name: model_y_name = body.get("model_y_name", "")

        prompt = body.get("prompt", "")
        response_x = body.get("response_x", "")
        response_y = body.get("response_y", "")
        tps_x = _body_num(body, "tps_x", 0.0, cast=float)
        tps_y = _body_num(body, "tps_y", 0.0, cast=float)
        latency_x = _body_num(body, "latency_x", 0.0, cast=float)
        latency_y = _body_num(body, "latency_y", 0.0, cast=float)
        agent_trace_x = body.get("agent_trace_x")
        agent_trace_y = body.get("agent_trace_y")

        if not model_a_name or not model_b_name or not voted_for or not model_x_name:
            raise HTTPException(400, f"Missing required vote parameters. Got: a={model_a_name}, b={model_b_name}, v={voted_for}, x={model_x_name}")

        # Resolve real names
        actual_model_x = model_a_name if model_x_name == "model_a" else model_b_name
        actual_model_y = model_a_name if model_y_name == "model_a" else model_b_name

        if voted_for == "x":
            score_x, score_y = 1.0, 0.0
            outcome = "a_wins"
        elif voted_for == "y":
            score_x, score_y = 0.0, 1.0
            outcome = "b_wins"
        else:
            score_x, score_y = 0.5, 0.5
            outcome = "draw"

        new_ra, new_rb = arena.elo.record_match(actual_model_x, actual_model_y, "playground", score_x, score_y)
        last_match_id = arena.elo.last_match_id()

        arena.elo.save_task_detail(
            match_id=last_match_id,
            task_id=f"play_{int(time.time())}",
            category="playground",
            difficulty="unknown",
            language="natural",
            instruction=prompt,
            response_a=response_x,
            response_b=response_y,
            expected="",
            score_a=score_x,
            score_b=score_y,
            outcome=outcome,
            tps_a=tps_x,
            tps_b=tps_y,
            latency_a=latency_x,
            latency_b=latency_y,
            tool_call_a=json.dumps(agent_trace_x) if agent_trace_x else None,
            tool_call_b=json.dumps(agent_trace_y) if agent_trace_y else None,
        )

        return {
            "status": "recorded",
            "model_x": actual_model_x,
            "model_y": actual_model_y,
            "elo_x_after": new_ra,
            "elo_y_after": new_rb,
        }

    # HF dataset
    @app.post("/api/pull_dataset")
    def api_pull(body: dict, tasks: BackgroundTasks):
        name = body.get("name")
        limit = body.get("limit")
        if not name:
            raise HTTPException(400, "name required")

        def _do():
            try:
                arena.load_hf_dataset(name, limit=limit)
            except Exception as e:
                log.error(f"[web] dataset {name}: {e}")
        tasks.add_task(_do)
        return {"started": True, "name": name}

    # ── Speculative Decoding API ──────────────────────────────────────────────
    from .backends.spec import SpecManager, SPEC_SERVERS, SpeculativeBackend
    import threading

    _spec_manager = SpecManager()
    # Guards against overlapping start_all sweeps (each one launches up to
    # len(SPEC_SERVERS) real GPU-loaded llama-server subprocesses, sequentially,
    # waiting up to 30s per server). Without this, a second call landing while
    # the first sweep is still mid-flight — including via the no-op limiter
    # path when slowapi isn't installed — could pile on a second full set of
    # launches concurrently with the first, racing on the same SpecManager
    # state and multiplying resource usage with no cap.
    _spec_start_all_lock = threading.Lock()
    _spec_start_all_running = {"value": False}

    @app.get("/api/spec/servers")
    def api_spec_servers():
        """Return status of all speculative decoding servers."""
        return _spec_manager.status()

    @app.post("/api/spec/start/{name}")
    def api_spec_start(name: str):
        if name not in SPEC_SERVERS:
            raise HTTPException(404, f"Unknown spec model: {name}. Available: {list(SPEC_SERVERS)}")
        result = _spec_manager.start(name)
        if not result.get("ok"):
            raise HTTPException(500, result.get("error", "Failed to start"))
        return result

    @app.post("/api/spec/stop/{name}")
    def api_spec_stop(name: str):
        if name not in SPEC_SERVERS:
            raise HTTPException(404, f"Unknown spec model: {name}. Available: {list(SPEC_SERVERS)}")
        return _spec_manager.stop(name)

    @app.post("/api/spec/stop_all")
    def api_spec_stop_all():
        return _spec_manager.stop_all()

    @app.post("/api/spec/start_all")
    @limiter.limit("1/minute")
    def api_spec_start_all(request: Request, tasks: BackgroundTasks):
        """Start all spec servers (sequentially, in background).

        Guarded against overlap: if a previous sweep is still running (it can
        take minutes — up to 30s per server, sequentially), reject the new
        request instead of launching a second concurrent sweep.
        """
        with _spec_start_all_lock:
            if _spec_start_all_running["value"]:
                raise HTTPException(
                    409,
                    "A start_all sweep is already in progress. "
                    "Wait for it to finish or check /api/spec/servers for current status.",
                )
            _spec_start_all_running["value"] = True

        def _do():
            try:
                for name in SPEC_SERVERS:
                    try:
                        _spec_manager.start(name)
                    except Exception as e:
                        log.error(f"[spec] start_all: {name} failed: {e}")
            finally:
                with _spec_start_all_lock:
                    _spec_start_all_running["value"] = False
        tasks.add_task(_do)
        return {"started": True, "count": len(SPEC_SERVERS)}

    @app.post("/api/spec/bench_all")
    @limiter.limit("2/minute")
    def api_spec_bench_all(request: Request, body: dict):
        """Benchmark every running spec server in parallel and return TPS/accept-rate stats."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        prompt = body.get("prompt", "Write a Python function that returns the nth Fibonacci number.")
        max_tokens = _body_num(body, "max_tokens", 512)
        running = [s for s in _spec_manager.status() if s["running"]]
        if not running:
            return {"results": [], "message": "No spec servers running."}

        def _bench(name):
            try:
                b = SpeculativeBackend(name)
                res = b.generate(name, prompt, max_tokens=max_tokens)
                return {
                    "name": name, "ok": res.ok,
                    "tps": res.tps, "latency_s": res.latency_s,
                    "tokens_out": res.tokens_out,
                    "spec_accept_rate": res.spec_accept_rate,
                    "error": res.error,
                }
            except Exception as e:
                return {"name": name, "ok": False, "tps": 0.0, "error": str(e)}

        results = []
        with ThreadPoolExecutor(max_workers=min(len(running), 4)) as ex:
            futures = {ex.submit(_bench, s["name"]): s["name"] for s in running}
            for fut in as_completed(futures):
                results.append(fut.result())
        # Sort by TPS descending
        results.sort(key=lambda r: r.get("tps", 0), reverse=True)
        return {"results": results, "prompt": prompt, "max_tokens": max_tokens}

    @app.post("/api/spec/vs_base")
    @limiter.limit("4/minute")
    def api_spec_vs_base(request: Request, body: dict):
        """Benchmark a spec model vs its Ollama base model on the same prompt."""
        name = body.get("model", "")
        prompt = body.get("prompt", "Write a Python function that returns the nth Fibonacci number.")
        max_tokens = _body_num(body, "max_tokens", 512)
        if name not in SPEC_SERVERS:
            raise HTTPException(404, f"Unknown spec model: {name}")
        cfg = SPEC_SERVERS[name]
        base_model = cfg["main"]
        spec_b = SpeculativeBackend(name)
        if not spec_b.is_alive():
            raise HTTPException(503, f"{name} server is not running on :{cfg['port']}")
        spec_res = spec_b.generate(name, prompt, max_tokens=max_tokens)
        base_res = arena.client.generate(base_model, prompt, num_predict=max_tokens)
        speedup = round(spec_res.tps / base_res.tps, 2) if base_res.tps else 0.0
        return {
            "spec": {
                "model": name, "tps": spec_res.tps, "latency_s": spec_res.latency_s,
                "tokens_out": spec_res.tokens_out, "accept_rate": spec_res.spec_accept_rate,
                "ok": spec_res.ok, "error": spec_res.error,
            },
            "base": {
                "model": base_model, "tps": base_res.tps, "latency_s": base_res.latency_s,
                "tokens_out": base_res.tokens_out, "ok": base_res.ok, "error": base_res.error,
            },
            "speedup": speedup,
            "prompt": prompt,
        }

    @app.post("/api/spec/stream")
    @limiter.limit(_RL_SPEC_STREAM)
    def api_spec_stream(request: Request, body: dict):
        """Server-Sent Events stream for live token-by-token generation."""
        import json as _json
        name = body.get("model", "")
        prompt = body.get("prompt", "")
        max_tokens = _body_num(body, "max_tokens", 1024)
        if name not in SPEC_SERVERS:
            raise HTTPException(404, f"Unknown spec model: {name}")
        b = SpeculativeBackend(name)
        if not b.is_alive():
            raise HTTPException(503, f"{name} server not running")

        def _gen():
            import requests as _rq, time as _t
            server_model = b._get_model_id()
            req_body = {
                "model": server_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "max_tokens": max_tokens,
                "stream": True,
                "stream_options": {"include_usage": True},
            }
            t0 = _t.time()
            ttft = 0.0
            tokens_out = 0
            first = True
            try:
                with _rq.post(
                    f"{b.base}/chat/completions",
                    json=req_body, headers=b._headers, stream=True, timeout=b.timeout,
                ) as r:
                    for line in r.iter_lines(decode_unicode=True):
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = _json.loads(data)
                        except Exception:
                            continue
                        usage = chunk.get("usage") or {}
                        timings = chunk.get("timings") or {}
                        choices = chunk.get("choices") or []
                        if choices:
                            delta = choices[0].get("delta", {}) or {}
                            piece = delta.get("content") or ""
                            if piece:
                                tokens_out += 1
                                if first:
                                    ttft = _t.time() - t0
                                    first = False
                                elapsed = _t.time() - t0
                                tps = tokens_out / elapsed if elapsed > 0 else 0.0
                                payload = {
                                    "type": "token", "piece": piece,
                                    "tokens_out": tokens_out, "tps": round(tps, 1),
                                    "elapsed": round(elapsed, 2), "ttft": round(ttft, 2),
                                }
                                yield f"data: {_json.dumps(payload)}\n\n"
                        if usage:
                            done = {
                                "type": "done",
                                "tokens_in": usage.get("prompt_tokens", 0),
                                "tokens_out": usage.get("completion_tokens", tokens_out),
                                "tps": round(
                                    usage.get("completion_tokens", tokens_out) /
                                    (timings.get("predicted_ms", 1) / 1000), 1
                                ) if timings.get("predicted_ms") else 0,
                                "latency_s": round(_t.time() - t0, 2),
                                "ttft": round(ttft, 2),
                            }
                            yield f"data: {_json.dumps(done)}\n\n"
            except Exception as e:
                yield f"data: {_json.dumps({'type':'error','error':str(e)})}\n\n"

        return StreamingResponse(_gen(), media_type="text/event-stream")

    @app.get("/api/spec/health/{name}")
    def api_spec_health(name: str):
        if name not in SPEC_SERVERS:
            raise HTTPException(404, f"Unknown spec server: {name}")
        b = SpeculativeBackend(name)
        return b.health()

    @app.post("/api/spec/generate")
    @limiter.limit(_RL_SPEC_STREAM)
    def api_spec_generate(request: Request, body: dict):
        """Single generation via a speculative decoding server (for benchmarking)."""
        name = body.get("model", "")
        prompt = body.get("prompt", "")
        if not name or not prompt:
            raise HTTPException(400, "model and prompt required")
        if name not in SPEC_SERVERS:
            raise HTTPException(404, f"Unknown spec model: {name}. Available: {list(SPEC_SERVERS)}")
        b = SpeculativeBackend(name)
        if not b.is_alive():
            raise HTTPException(503, f"{name} server is not running on port {b.port}")
        res = b.generate(name, prompt, **{k: v for k, v in body.items() if k not in ("model", "prompt")})
        return {
            "model": res.model,
            "text": res.text,
            "tps": res.tps,
            "latency_s": res.latency_s,
            "time_to_first": res.time_to_first,
            "tokens_in": res.tokens_in,
            "tokens_out": res.tokens_out,
            "spec_accept_rate": res.spec_accept_rate,
            "ok": res.ok,
            "error": res.error,
        }

    # ── Genome Explorer API ───────────────────────────────────────────────────
    try:
        from .genome.db import GenomeStore as _GenomeStore
        from .genome.registry import CanonicalRegistry as _CanonicalRegistry
        from .genome.scanner import OllamaScanner as _OllamaScanner
        from .genome.resolver import GenomeResolver as _GenomeResolver
        from .genome.graph import GraphEngine as _GraphEngine

        _genome_db_path = db_path.replace("arena.db", "genome.db")
        _genome_store = _GenomeStore(db_path=_genome_db_path)
        _genome_registry = _CanonicalRegistry()
        _genome_resolver = _GenomeResolver(store=_genome_store, registry=_genome_registry)
        _genome_graph = _GraphEngine(_genome_store)
        _genome_scan_state: dict = {
            "running": False, "current": 0, "total": 0, "model": "", "done": False,
        }

        @app.get("/genome")
        async def genome_page_redirect():
            # Genome Explorer is a dashboard tab now, not a standalone page —
            # redirect old bookmarks/links straight to it instead of serving
            # a second, differently-styled page.
            return RedirectResponse(url="/#genome")

        @app.get("/api/hardware/scan", summary="Hardware-aware model fit scan",
                 description="Scans this machine's RAM and scores every installed "
                             "model by how well it fits (0-100%), with a tokens/sec "
                             "estimate (measured if this model has been benchmarked "
                             "before, otherwise scaled from the fastest measured "
                             "model on this machine). Also returns the two "
                             "best-fitting models for default pre-selection.")
        def api_hardware_scan():
            from .hardware_fit import hardware_summary, score_models
            models = score_models(ollama_url, db_path=db_path)
            return {
                "hardware": hardware_summary(ollama_url),
                "models": models,
                "best_two": [m["model"] for m in models[:2]],
            }

        @app.get("/api/genome/tree")
        async def genome_tree(model: str | None = None):
            if model:
                gid = _genome_registry.match_by_name(model)
                data = _genome_graph.subtree(gid or model)
            else:
                data = _genome_graph.to_d3()
            return JSONResponse(data)

        @app.get("/api/genome/local")
        async def genome_local():
            return JSONResponse({"models": _genome_store.list_local()})

        @app.post("/api/genome/scan")
        async def genome_scan(background_tasks: BackgroundTasks):
            _genome_scan_state.update({
                "running": True, "current": 0, "total": 0, "model": "", "done": False,
            })

            # _do_scan (below) runs via BackgroundTasks in a worker thread, which
            # has no running event loop of its own — asyncio.get_event_loop()
            # there either raises or returns a non-running loop, so
            # loop.is_running() is always False and the broadcast silently never
            # fires (the broad except swallowed the raise, masking the bug).
            # Capture *this* request's running loop while we're still in async
            # context, then hand events back to it from the worker thread via
            # run_coroutine_threadsafe.
            import asyncio
            _loop = asyncio.get_running_loop()

            def _emit(event: dict):
                try:
                    asyncio.run_coroutine_threadsafe(manager.broadcast(event), _loop)
                except Exception:
                    pass

            def _do_scan():
                def on_scan(i, total, name):
                    _genome_scan_state.update({
                        "running": True, "current": i, "total": total, "model": name,
                    })
                    _emit({
                        "type": "genome_scan_progress",
                        "current": i, "total": total, "model": name,
                    })

                def on_resolve(i, total, name):
                    _genome_scan_state.update({
                        "running": True, "current": i, "total": total, "model": name,
                        "phase": "resolve",
                    })
                    _emit({
                        "type": "genome_scan_progress",
                        "phase": "resolve", "current": i, "total": total, "model": name,
                    })

                scanner = _OllamaScanner(ollama_url=ollama_url)
                local = scanner.scan_local(on_progress=on_scan)
                _genome_resolver.scan_and_resolve_all(local, on_progress=on_resolve)
                _genome_scan_state.update({
                    "running": False, "done": True,
                    "current": len(local), "total": len(local),
                })
                _emit({"type": "genome_scan_complete", "count": len(local)})

            background_tasks.add_task(_do_scan)
            return JSONResponse({"started": True})

        @app.get("/api/genome/scan/progress")
        async def genome_scan_progress():
            return JSONResponse(dict(_genome_scan_state))

        @app.get("/api/genome/model/{model_name:path}")
        async def genome_model(model_name: str):
            gid = _genome_registry.match_by_name(model_name)
            canonical = _genome_registry.get(gid) if gid else None
            local_rows = _genome_store.list_local()
            local_match = next((r for r in local_rows if r["name"] == model_name), None)
            return JSONResponse({"canonical": canonical, "local": local_match})

        @app.get("/api/agent_trace/{match_id}")
        async def agent_trace(match_id: int):
            import json as _json
            tasks = arena.elo.tasks_for_match(match_id)
            result = []
            for t in tasks:
                trace_a, trace_b = None, None
                raw_a = t.get("tool_call_a")
                raw_b = t.get("tool_call_b")
                try:
                    trace_a = _json.loads(raw_a) if raw_a else None
                except (_json.JSONDecodeError, TypeError):
                    pass
                try:
                    trace_b = _json.loads(raw_b) if raw_b else None
                except (_json.JSONDecodeError, TypeError):
                    pass
                result.append({
                    "task_id": t["task_id"],
                    "category": t.get("category"),
                    "instruction": t.get("instruction", "")[:200],
                    "score_a": t.get("score_a"),
                    "score_b": t.get("score_b"),
                    "trace_a": trace_a,
                    "trace_b": trace_b,
                })
            return JSONResponse({"match_id": match_id, "tasks": result})

    except ImportError as _e:
        import logging as _logging
        _logging.getLogger("arena.web").warning(f"Genome API unavailable: {_e}")

    # ── Simulations API ────────────────────────────────────────────────────────
    try:
        from .simulations.core.runner import SimulationManager
        from .simulations.core.scenario import list_scenarios
        from .simulations.core.types import AgentSpec
        from .simulations.replay.player import ReplayPlayer

        _sim_db_path = db_path.replace("arena.db", "sim.db")
        _sim_manager = SimulationManager(db_path=_sim_db_path)
        # Tracks the specific SimulationManager instance executing each
        # in-flight run, so a later POST .../pause request (a different HTTP
        # request, but the same process) flips the _paused flag on the same
        # instance the background thread's start_run() loop is checking --
        # not some other instance's separate flag.
        _sim_active_managers: dict[str, SimulationManager] = {}

        def _agent_specs_from_models(models: list[str], router_role: str | None = None) -> list[AgentSpec]:
            counts: dict[str, int] = {}
            specs = []
            for m in models:
                counts[m] = counts.get(m, 0) + 1
                suffix = f"_{counts[m]}" if counts[m] > 1 else ""
                specs.append(AgentSpec(agent_id=f"{m}{suffix}", model=m, router_role=router_role))
            return specs

        @app.get("/api/sim/scenarios")
        async def sim_scenarios():
            return JSONResponse([
                {"name": s.name, "description": s.description, "default_config": s.default_config}
                for s in sorted(list_scenarios(), key=lambda s: s.name)
            ])

        @app.get("/api/sim/runs")
        async def sim_runs_list(scenario: str | None = None):
            return JSONResponse(_sim_manager.store.list_runs(scenario))

        @app.get("/api/sim/compare")
        async def sim_compare(run_ids: str):
            from .simulations.eval.compare import compare_runs
            ids = [r.strip() for r in run_ids.split(",") if r.strip()]
            if len(ids) < 1:
                raise HTTPException(400, "run_ids must be a comma-separated list of at least 1 run id")
            report = compare_runs(ids, db_path=_sim_db_path)
            return JSONResponse({
                "run_ids": report.run_ids, "scenario": report.scenario,
                "metric_names": report.metric_names, "metrics_by_run": report.metrics_by_run,
                "best_run_by_metric": {
                    name: report.best_run(name) for name in report.metric_names
                },
            })

        @app.post("/api/sim/run")
        async def sim_run_start(body: dict, background_tasks: BackgroundTasks):
            scenario = body.get("scenario")
            models = body.get("agents") or []
            if not scenario or not isinstance(models, list) or not models:
                raise HTTPException(400, "scenario and a non-empty agents list are required")
            config = body.get("config") or {}
            max_ticks = _body_num(body, "ticks", 1000)

            # router_role is opt-in (set from the sim tab's "Use role
            # routing" picker) -- only then do agents resolve their model
            # via the saved /api/role-routing config instead of the
            # literal --agents-equivalent model strings above.
            router_role = body.get("router_role")
            router = None
            if router_role:
                role_models = _load_role_models()
                if role_models:
                    from .model_router import RoleRouter
                    router = RoleRouter(role_models=role_models)

            mgr = SimulationManager(db_path=_sim_db_path, router=router)
            try:
                run_id = mgr.create_run(
                    scenario, _agent_specs_from_models(models, router_role=router_role),
                    config=config, seed=body.get("seed"),
                )
            except KeyError as e:
                raise HTTPException(404, str(e))
            _sim_active_managers[run_id] = mgr

            import asyncio
            _loop = asyncio.get_running_loop()

            def _emit(event: dict):
                try:
                    asyncio.run_coroutine_threadsafe(manager.broadcast(event), _loop)
                except Exception:
                    pass

            def _do_run():
                try:
                    result = mgr.start_run(
                        run_id,
                        on_tick=lambda d: _emit({"type": "sim_tick", **d}),
                        max_ticks=max_ticks,
                    )
                    _emit({
                        "type": "sim_run_done", "run_id": run_id,
                        "terminated": result.terminated, "truncated": result.truncated,
                        "outcome": result.outcome, "metrics": result.metrics,
                    })
                except Exception as e:
                    _emit({"type": "sim_run_done", "run_id": run_id, "error": str(e)})
                finally:
                    _sim_active_managers.pop(run_id, None)

            background_tasks.add_task(_do_run)
            return JSONResponse({"run_id": run_id})

        @app.get("/api/sim/run/{run_id}")
        async def sim_run_get(run_id: str):
            run = _sim_manager.store.get_run(run_id)
            if run is None:
                raise HTTPException(404, f"no run found with id {run_id}")
            metrics = {m["metric_name"]: m["value"] for m in _sim_manager.store.get_metrics(run_id)}
            return JSONResponse({**run, "metrics": metrics})

        @app.post("/api/sim/run/{run_id}/pause")
        async def sim_run_pause(run_id: str):
            mgr = _sim_active_managers.get(run_id, _sim_manager)
            try:
                mgr.pause_run(run_id)
            except KeyError as e:
                raise HTTPException(404, str(e))
            await manager.broadcast({"type": "sim_phase_change", "run_id": run_id, "status": "paused"})
            return JSONResponse({"run_id": run_id, "status": "paused"})

        @app.post("/api/sim/run/{run_id}/resume")
        async def sim_run_resume(run_id: str, body: dict, background_tasks: BackgroundTasks):
            if _sim_manager.store.get_run(run_id) is None:
                raise HTTPException(404, f"no run found with id {run_id}")
            max_ticks = _body_num(body, "ticks", 1000)

            mgr = SimulationManager(db_path=_sim_db_path)
            _sim_active_managers[run_id] = mgr

            import asyncio
            _loop = asyncio.get_running_loop()

            def _emit(event: dict):
                try:
                    asyncio.run_coroutine_threadsafe(manager.broadcast(event), _loop)
                except Exception:
                    pass

            def _do_resume():
                try:
                    result = mgr.resume_run(
                        run_id,
                        on_tick=lambda d: _emit({"type": "sim_tick", **d}),
                        max_ticks=max_ticks,
                    )
                    _emit({
                        "type": "sim_run_done", "run_id": run_id,
                        "terminated": result.terminated, "truncated": result.truncated,
                        "outcome": result.outcome, "metrics": result.metrics,
                    })
                except Exception as e:
                    _emit({"type": "sim_run_done", "run_id": run_id, "error": str(e)})
                finally:
                    _sim_active_managers.pop(run_id, None)

            background_tasks.add_task(_do_resume)
            return JSONResponse({"run_id": run_id, "status": "resuming"})

        @app.get("/api/sim/run/{run_id}/replay")
        async def sim_run_replay(run_id: str, tick: int | None = None):
            player = ReplayPlayer(run_id, db_path=_sim_db_path)
            events = player.seek(tick) if tick is not None else player.all_events()
            return JSONResponse([
                {"id": e.id, "tick": e.tick, "kind": e.kind, "payload": e.payload, "actor_id": e.actor_id}
                for e in events
            ])

        @app.get("/api/sim/run/{run_id}/trace")
        async def sim_run_trace(run_id: str, limit: int = 300):
            run = _sim_manager.store.get_run(run_id)
            if run is None:
                raise HTTPException(404, f"no run found with id {run_id}")
            bounded_limit = max(1, min(limit, 1000))
            transitions = _sim_manager.store.get_transitions(run_id)[-bounded_limit:]
            events = _sim_manager.store.get_events(run_id)[-bounded_limit:]
            return JSONResponse({
                "run": run,
                "transitions": transitions,
                "events": [
                    {
                        "id": event.id,
                        "tick": event.tick,
                        "kind": event.kind,
                        "payload": event.payload,
                        "actor_id": event.actor_id,
                        "visibility": (
                            "public" if event.witness_ids == frozenset({"*"}) else "private"
                        ),
                    }
                    for event in events
                ],
            })

        @app.post("/api/sim/train")
        async def sim_train(body: dict, background_tasks: BackgroundTasks):
            from .simulations.training.dataset import export_run_to_jsonl, load_jsonl
            from .simulations.training.imitation import ImitationConfig, train_imitation

            run_id = body.get("run_id")
            if not run_id:
                raise HTTPException(400, "run_id required")
            epochs = _body_num(body, "epochs", 5)

            jid = _new_job_id()
            jobs[jid] = {"status": "running", "run_id": run_id, "created_at": time.time()}

            import asyncio
            _loop = asyncio.get_running_loop()

            def _emit(event: dict):
                try:
                    asyncio.run_coroutine_threadsafe(manager.broadcast(event), _loop)
                except Exception:
                    pass

            def _do_train():
                _emit({"type": "sim_training_progress", "job_id": jid, "run_id": run_id, "status": "started"})
                tmp_path = f"/tmp/sim_train_{run_id}.jsonl"
                n = export_run_to_jsonl(run_id, tmp_path, db_path=_sim_db_path)
                if n == 0:
                    jobs[jid]["status"] = "error"
                    jobs[jid]["error"] = "no transitions found for this run"
                    _emit({"type": "sim_training_progress", "job_id": jid, "run_id": run_id,
                           "status": "error", "error": jobs[jid]["error"]})
                    return
                rows = load_jsonl(tmp_path)
                try:
                    result = train_imitation(rows, config=ImitationConfig(epochs=epochs))
                except (ValueError, RuntimeError) as e:
                    jobs[jid]["status"] = "error"
                    jobs[jid]["error"] = str(e)
                    _emit({"type": "sim_training_progress", "job_id": jid, "run_id": run_id,
                           "status": "error", "error": str(e)})
                    return
                jobs[jid]["status"] = "done"
                jobs[jid]["result"] = {
                    "kind_vocab": result.kind_vocab, "final_loss": result.final_loss,
                    "losses_by_epoch": result.losses_by_epoch,
                }
                _emit({"type": "sim_training_progress", "job_id": jid, "run_id": run_id,
                       "status": "done", **jobs[jid]["result"]})

            background_tasks.add_task(_do_train)
            return JSONResponse({"job_id": jid})

    except ImportError as _e:
        import logging as _logging
        _logging.getLogger("arena.web").warning(f"Simulations API unavailable: {_e}")

    from ._banner import print_banner
    print_banner(__version__)
    print(f"  backend: {arena.client.name}")
    print(f"  url:     http://{host if host != '0.0.0.0' else 'localhost'}:{port}\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")
