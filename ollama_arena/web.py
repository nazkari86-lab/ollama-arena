"""FastAPI dashboard. Requires [web] (fastapi, uvicorn). Charts require [viz]."""
from __future__ import annotations
import logging
from pathlib import Path

log = logging.getLogger("arena.web")


def run_web(
    host: str = "0.0.0.0",
    port: int = 7860,
    ollama_url: str = "http://localhost:11434",
    db_path: str = "arena.db",
    backend: str | None = None,
    api_key: str | None = None,
):
    try:
        from fastapi import FastAPI, BackgroundTasks, HTTPException
        from fastapi.responses import HTMLResponse, JSONResponse
        import uvicorn
    except ImportError:
        raise RuntimeError("Install: pip install 'ollama-arena[web]'")

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

    app = FastAPI(title="Ollama Arena", version="2.0.0")
    HERE = Path(__file__).parent.parent / "templates"

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse((HERE / "index.html").read_text())

    @app.get("/api/leaderboard")
    def api_leaderboard():
        return arena.leaderboard()

    @app.get("/api/history")
    def api_history(limit: int = 50):
        return arena.match_history(limit=limit)

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

    @app.get("/charts/leaderboard")
    def chart_lb():
        return HTMLResponse(leaderboard_table_html(arena.leaderboard()))

    # Run a match
    @app.post("/api/match")
    def api_run_match(body: dict, tasks: BackgroundTasks):
        ma = body.get("model_a", ""); mb = body.get("model_b", "")
        cat = body.get("category", "coding"); n = int(body.get("n", 5))
        if not ma or not mb:
            raise HTTPException(400, "model_a and model_b required")
        jid = f"{ma}_vs_{mb}_{cat}_{n}"
        jobs[jid] = {"status": "running", "log": [], "model_a": ma, "model_b": mb}

        def _run():
            def on_task(tid, sa, sb, outcome):
                jobs[jid]["log"].append({
                    "task_id": tid, "score_a": sa, "score_b": sb, "outcome": outcome
                })
            arena._on_task_done = on_task
            try:
                r = arena.run_match(ma, mb, category=cat, n=n)
                jobs[jid]["status"] = "done"
                jobs[jid]["result"] = {
                    "a_wins": r.a_wins, "b_wins": r.b_wins, "draws": r.draws,
                    "elo_a_after": r.elo_a_after, "elo_b_after": r.elo_b_after,
                    "duration_s": r.duration_s,
                }
            except Exception as e:
                jobs[jid]["status"] = "error"
                jobs[jid]["error"] = str(e)

        tasks.add_task(_run)
        return {"job_id": jid}

    @app.get("/api/job/{job_id}")
    def api_job(job_id: str):
        return jobs.get(job_id, {"status": "not_found"})

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

    from ._banner import print_banner
    from . import __version__
    print_banner(__version__)
    print(f"  backend: {arena.client.name}")
    print(f"  url:     http://{host if host != '0.0.0.0' else 'localhost'}:{port}\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")
