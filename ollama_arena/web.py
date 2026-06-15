"""
FastAPI web dashboard for ollama-arena.
Install extras: pip install 'ollama-arena[web]'
"""
from __future__ import annotations
import json, os, threading
from pathlib import Path

try:
    from fastapi import FastAPI, BackgroundTasks
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    import uvicorn
    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False


def run_web(host: str = "0.0.0.0", port: int = 7860,
            ollama_url: str = "http://localhost:11434",
            db_path: str = "arena.db"):
    if not _HAS_FASTAPI:
        raise ImportError("fastapi and uvicorn required: pip install 'ollama-arena[web]'")

    from .arena import Arena
    from .tasks import list_categories, task_stats

    arena = Arena(ollama_url=ollama_url, db_path=db_path)
    active_jobs: dict[str, dict] = {}

    app = FastAPI(title="Ollama Arena", version="1.0.0")

    _HERE = Path(__file__).parent.parent / "templates"

    @app.get("/", response_class=HTMLResponse)
    def index():
        html = (_HERE / "index.html").read_text()
        return HTMLResponse(html)

    @app.get("/api/leaderboard")
    def leaderboard():
        return arena.leaderboard()

    @app.get("/api/history")
    def history(limit: int = 30):
        return arena.match_history(limit=limit)

    @app.get("/api/models")
    def models():
        return arena.client.list_models()

    @app.get("/api/categories")
    def categories():
        return {"categories": list_categories(), "stats": task_stats()}

    @app.post("/api/match")
    def start_match(body: dict, background_tasks: BackgroundTasks):
        model_a = body.get("model_a", "")
        model_b = body.get("model_b", "")
        category = body.get("category", "coding")
        n = int(body.get("n", 5))

        if not model_a or not model_b:
            return JSONResponse({"error": "model_a and model_b required"}, status_code=400)

        job_id = f"{model_a}_vs_{model_b}_{category}"
        active_jobs[job_id] = {"status": "running", "log": []}

        def _run():
            def on_task(task_id, score_a, score_b, outcome):
                active_jobs[job_id]["log"].append({
                    "task_id": task_id, "score_a": score_a,
                    "score_b": score_b, "outcome": outcome,
                })
            arena._on_task_done = on_task
            try:
                result = arena.run_match(model_a, model_b, category=category, n=n)
                active_jobs[job_id]["status"] = "done"
                active_jobs[job_id]["result"] = {
                    "a_wins": result.a_wins, "b_wins": result.b_wins, "draws": result.draws,
                    "elo_a_after": result.elo_a_after, "elo_b_after": result.elo_b_after,
                }
            except Exception as e:
                active_jobs[job_id]["status"] = "error"
                active_jobs[job_id]["error"] = str(e)

        background_tasks.add_task(_run)
        return {"job_id": job_id, "status": "started"}

    @app.get("/api/job/{job_id}")
    def job_status(job_id: str):
        return active_jobs.get(job_id, {"status": "not_found"})

    print(f"\n  🏟️  Ollama Arena Web UI")
    print(f"  → http://{host if host != '0.0.0.0' else 'localhost'}:{port}\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")
