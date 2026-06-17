"""FastAPI dashboard. Requires [web] (fastapi, uvicorn). Charts require [viz]."""
# NOTE: do NOT add `from __future__ import annotations` here. With PEP 563
# active, FastAPI's `get_type_hints()` would resolve annotations against the
# MODULE globals and fail to see `Request` / `BackgroundTasks` (they're
# imported inside `run_web`'s try/except). The visible effect was every
# route's `request: Request` being misclassified as a query parameter.
import json, logging, os, time
from pathlib import Path

# Imported at module scope so annotation resolution in run_web() succeeds.
# These are no-cost imports; FastAPI is already required for this module.
try:
    from fastapi import (
        FastAPI, BackgroundTasks, HTTPException, Request,
        WebSocket, WebSocketDisconnect,
    )
    from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
    from fastapi.middleware.cors import CORSMiddleware
    from starlette.middleware.base import BaseHTTPMiddleware
except ImportError:
    # Allow `import ollama_arena.web` even when [web] extras aren't installed
    # — run_web() will raise the same friendly error when actually called.
    FastAPI = BackgroundTasks = HTTPException = Request = None       # type: ignore
    WebSocket = WebSocketDisconnect = None                            # type: ignore
    HTMLResponse = JSONResponse = StreamingResponse = None            # type: ignore
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


def run_web(
    host: str = "0.0.0.0",
    port: int = 7860,
    ollama_url: str = "http://localhost:11434",
    db_path: str = "arena.db",
    backend: str | None = None,
    api_key: str | None = None,
):
    if FastAPI is None:
        raise RuntimeError("Install: pip install 'ollama-arena[web]'")
    import uvicorn

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
    jobs: dict[str, dict] = {}

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
            try:
                # Need an event loop to close gracefully, but disconnect is often sync
                # We'll just suppress errors if the socket is already dead
                pass 
            except Exception:
                pass

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
            response = await call_next(request)
            # Strict-ish CSP. Allows the CDN scripts we ship (plotly, three,
            # highlight, DOMPurify), Google Fonts, and self. No inline event
            # handlers, no eval (DOMPurify doesn't need it).
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' "
                "  https://cdn.plot.ly https://cdnjs.cloudflare.com "
                "  https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' "
                "  https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com data:; "
                "img-src 'self' data: blob: https:; "
                "connect-src 'self' ws: wss:; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "object-src 'none'; "
                "form-action 'self';"
            )
            response.headers["X-Frame-Options"]        = "DENY"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"]        = "no-referrer"
            response.headers["Permissions-Policy"]     = (
                "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
                "microphone=(), payment=(), usb=()"
            )
            response.headers["X-XSS-Protection"]       = "0"   # CSP is the right tool
            return response
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse((HERE / "index.html").read_text())

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

    @app.get("/api/history")
    def api_history(limit: int = 50):
        now = time.time()
        c = _hist_cache.get(limit)
        if c and now - c["t"] < 1.0:
            return c["data"]
        data = arena.match_history(limit=limit)
        _hist_cache[limit] = {"t": now, "data": data}
        return data

    @app.get("/api/models")
    def api_models():
        return arena.client.list_models()

    @app.get("/api/categories")
    def api_categories():
        return {"categories": list_categories(),
                "languages": list_languages(),
                "stats": task_stats()}

    @app.get("/api/perf")
    def api_perf():
        return arena.performance_stats()

    @app.get("/api/datasets")
    def api_datasets():
        return available_datasets()

    @app.get("/api/version")
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
        ma = body.get("model_a", "").strip()
        mb = body.get("model_b", "").strip()
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
        cat = body.get("category", "coding"); n = int(body.get("n", 5))
        concurrency = int(body.get("concurrency", 1))
        if not ma or not mb:
            raise HTTPException(400, "model_a and model_b required")
        jid = f"{ma}_vs_{mb}_{cat}_{n}_{int(time.time())}"
        jobs[jid] = {"status": "running", "log": [], "model_a": ma, "model_b": mb}

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
        return jobs.get(job_id, {"status": "not_found"})

    @app.post("/api/tournament")
    @limiter.limit(_RL_TOURNAMENT)
    def api_run_tournament(request: Request, body: dict, tasks: BackgroundTasks):
        models = body.get("models", [])
        cat = body.get("category", "coding")
        n = int(body.get("n", 3))
        concurrency = int(body.get("concurrency", 1))

        if len(models) < 2:
            raise HTTPException(400, "At least 2 models required for a tournament")

        jid = f"tourney_{cat}_{n}_{int(time.time())}"
        jobs[jid] = {"status": "running", "log": [], "type": "tournament", "models": models}

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
    def api_playground_vote(body: dict):
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
        tps_x = float(body.get("tps_x", 0.0))
        tps_y = float(body.get("tps_y", 0.0))
        latency_x = float(body.get("latency_x", 0.0))
        latency_y = float(body.get("latency_y", 0.0))
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

    _spec_manager = SpecManager()

    @app.get("/api/spec/servers")
    def api_spec_servers():
        """Return status of all speculative decoding servers."""
        return _spec_manager.status()

    @app.post("/api/spec/start/{name}")
    def api_spec_start(name: str):
        result = _spec_manager.start(name)
        if not result.get("ok"):
            raise HTTPException(500, result.get("error", "Failed to start"))
        return result

    @app.post("/api/spec/stop/{name}")
    def api_spec_stop(name: str):
        return _spec_manager.stop(name)

    @app.post("/api/spec/stop_all")
    def api_spec_stop_all():
        return _spec_manager.stop_all()

    @app.post("/api/spec/start_all")
    @limiter.limit("1/minute")
    def api_spec_start_all(request: Request, tasks: BackgroundTasks):
        """Start all spec servers (sequentially, in background)."""
        def _do():
            for name in SPEC_SERVERS:
                try:
                    _spec_manager.start(name)
                except Exception as e:
                    log.error(f"[spec] start_all: {name} failed: {e}")
        tasks.add_task(_do)
        return {"started": True, "count": len(SPEC_SERVERS)}

    @app.post("/api/spec/bench_all")
    @limiter.limit("2/minute")
    def api_spec_bench_all(request: Request, body: dict):
        """Benchmark every running spec server in parallel and return TPS/accept-rate stats."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        prompt = body.get("prompt", "Write a Python function that returns the nth Fibonacci number.")
        max_tokens = int(body.get("max_tokens", 512))
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
        max_tokens = int(body.get("max_tokens", 512))
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
        max_tokens = int(body.get("max_tokens", 1024))
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

    from ._banner import print_banner
    print_banner(__version__)
    print(f"  backend: {arena.client.name}")
    print(f"  url:     http://{host if host != '0.0.0.0' else 'localhost'}:{port}\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")
