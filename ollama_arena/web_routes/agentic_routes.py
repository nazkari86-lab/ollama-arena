"""Web routes for the agentic/ module (sandboxes + swarm battles).

Exposes the same operations as `ollama-arena sandbox`/`swarm` CLI
commands (see cli/agentic.py) over HTTP, using identical safe defaults --
the web path never accepts custom SandboxConfig overrides (network
isolation, seccomp, etc. always stay on), so it carries the same safety
gating as the CLI rather than a weaker one.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import asdict
from typing import Callable

from fastapi import APIRouter, BackgroundTasks, HTTPException

from ..agentic.sandbox import SandboxConfig, SandboxManager
from ..agentic.swarm import SwarmBattle, example_2v2_setup, example_3v3_setup


def build_agentic_router(
    arena,
    jobs: dict,
    manager,
    new_job_id: Callable[[], str],
    body_num: Callable,
    sandbox_config: SandboxConfig | None = None,
) -> APIRouter:
    """`sandbox_config` overrides SandboxManager's default (DOCKER, falling
    back to MOCK only if no `docker` binary is found) -- used by tests to
    force the deterministic MOCK backend regardless of the test machine's
    local Docker install. web.py's call site leaves it None, matching the
    `ollama-arena sandbox` CLI command's default."""
    router = APIRouter(prefix="/api/agentic", tags=["agentic"])

    # One SandboxManager per process -- mirrors the CLI's per-invocation
    # manager, but persists across requests so list/execute/stop can
    # operate on sandboxes created by earlier requests in this session.
    sandbox_manager = SandboxManager(sandbox_config)

    @router.get("/sandboxes")
    def list_sandboxes():
        return [
            {"sandbox_id": sid, "status": sandbox_manager.get_sandbox_status(sid).value}
            for sid in sandbox_manager.list_sandboxes()
        ]

    @router.post("/sandbox/start")
    def start_sandbox(body: dict):
        sandbox_id = str(body.get("sandbox_id") or "").strip()
        if not sandbox_id:
            raise HTTPException(400, "sandbox_id is required")
        try:
            instance = sandbox_manager.create_sandbox(sandbox_id)
        except RuntimeError as e:
            raise HTTPException(503, str(e))
        return {
            "sandbox_id": instance.sandbox_id,
            "status": instance.status.value,
            "backend": instance.config.backend.value,
        }

    @router.post("/sandbox/{sandbox_id}/execute")
    def execute_in_sandbox(sandbox_id: str, body: dict):
        task = str(body.get("task") or "").strip()
        if not task:
            raise HTTPException(400, "task is required")
        result = sandbox_manager.execute_task(sandbox_id, task)
        return asdict(result)

    @router.post("/sandbox/{sandbox_id}/stop")
    def stop_sandbox(sandbox_id: str):
        if not sandbox_manager.stop_sandbox(sandbox_id):
            raise HTTPException(404, f"sandbox {sandbox_id!r} not found")
        return {"ok": True}

    @router.post("/sandbox/{sandbox_id}/cleanup")
    def cleanup_sandbox(sandbox_id: str):
        if not sandbox_manager.cleanup_sandbox(sandbox_id):
            raise HTTPException(404, f"sandbox {sandbox_id!r} not found")
        return {"ok": True}

    @router.post("/swarm/start")
    async def start_swarm(body: dict, background_tasks: BackgroundTasks):
        mode = str(body.get("mode") or "2v2")
        task = str(body.get("task") or "").strip()
        if not task:
            raise HTTPException(400, "task is required")
        rounds = body_num(body, "rounds", 3)
        max_steps = body_num(body, "max_steps", 5)

        if mode == "2v2":
            team_a_config, team_b_config = example_2v2_setup()
        elif mode == "3v3":
            team_a_config, team_b_config = example_3v3_setup()
        else:
            raise HTTPException(400, "mode must be '2v2' or '3v3'")

        if not arena.client.is_alive():
            raise HTTPException(503, "Backend not reachable")

        job_id = new_job_id()
        jobs[job_id] = {"status": "running", "type": "swarm_battle", "created_at": time.time()}

        battle = SwarmBattle(arena.client, arena.mcp)
        team_a = battle.create_team("Team A", team_a_config)
        team_b = battle.create_team("Team B", team_b_config)

        loop = asyncio.get_running_loop()

        def _emit(event: dict):
            try:
                asyncio.run_coroutine_threadsafe(manager.broadcast(event), loop)
            except Exception:
                pass

        def _do_run():
            try:
                result = battle.run_battle(
                    team_a, team_b, task, rounds=rounds, max_steps_per_round=max_steps,
                )
                jobs[job_id] = {
                    "status": "done", "type": "swarm_battle",
                    "created_at": jobs[job_id]["created_at"],
                    "winner": result.winner,
                    "team_a_score": result.team_a_score, "team_b_score": result.team_b_score,
                    "duration_s": result.duration_s, "rounds_completed": result.rounds_completed,
                    "collaboration_metrics": result.collaboration_metrics,
                }
                _emit({"type": "swarm_battle_done", "job_id": job_id, "winner": result.winner})
            except Exception as e:
                jobs[job_id] = {
                    "status": "error", "type": "swarm_battle",
                    "created_at": jobs[job_id]["created_at"], "error": str(e),
                }
                _emit({"type": "swarm_battle_done", "job_id": job_id, "error": str(e)})

        background_tasks.add_task(_do_run)
        return {"job_id": job_id}

    @router.get("/swarm/{job_id}")
    def get_swarm_job(job_id: str):
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        return job

    return router
