"""Additional FastAPI endpoint tests to raise web.py coverage above 60%.

Targets routes not covered in test_web_api.py:
  POST /api/match, POST /api/tournament, POST /api/royale
  POST /api/strategy, POST /api/playground/*
  GET  /api/models/{model}/caps
  POST /api/retry_task/{id}, GET /api/export_match/{id}, GET /api/export_royale/{id}
  POST /api/pull_dataset, GET /api/spec/servers
"""
from __future__ import annotations

import unittest.mock as mock

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# Shared fixture
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def _app2(tmp_path_factory):
    pytest.importorskip("fastapi")
    pytest.importorskip("uvicorn")

    db = tmp_path_factory.mktemp("webapi2") / "arena2_test.db"
    captured: dict = {}

    def _fake_uvicorn_run(app, **_kw):
        captured["app"] = app

    import ollama_arena.web as _web_mod

    with (
        mock.patch("uvicorn.run", side_effect=_fake_uvicorn_run),
        mock.patch.object(_web_mod, "_RL_DEFAULT", "10000/minute"),
        mock.patch.object(_web_mod, "_RL_MATCH", "10000/minute"),
        mock.patch.object(_web_mod, "_RL_TOURNAMENT", "10000/minute"),
        mock.patch.object(_web_mod, "_RL_PLAYGROUND", "10000/minute"),
        mock.patch.object(_web_mod, "_RL_SPEC_STREAM", "10000/minute"),
        mock.patch(
            "ollama_arena.backends.ollama.OllamaBackend.list_models",
            return_value=["llama3", "phi3"],
        ),
    ):
        from ollama_arena.web import run_web
        run_web(host="127.0.0.1", port=19_998, db_path=str(db))

    assert "app" in captured, "uvicorn.run was not called — app not built"
    return captured["app"]


@pytest.fixture(scope="module")
def client2(_app2):
    from starlette.testclient import TestClient
    return TestClient(_app2, raise_server_exceptions=False)


def _mock_gen_result(text="Hello", tps=10.0, latency=0.1):
    """Return a real GenResult-like mock that satisfies ok=True."""
    from ollama_arena.backends.base import GenResult
    return GenResult(text=text, model="llama3", tps=tps, latency_s=latency)


# ──────────────────────────────────────────────────────────────────────────────
# Model capabilities
# ──────────────────────────────────────────────────────────────────────────────

class TestModelCaps:
    def test_caps_200(self, client2):
        caps = {"vision": False, "tools": True, "ctx_length": 4096}
        with mock.patch("ollama_arena.model_caps.get", return_value=caps):
            r = client2.get("/api/models/llama3/caps")
        assert r.status_code == 200

    def test_caps_returns_dict(self, client2):
        caps = {"vision": False, "tools": True, "ctx_length": 4096}
        with mock.patch("ollama_arena.model_caps.get", return_value=caps):
            data = client2.get("/api/models/llama3/caps").json()
        assert isinstance(data, dict)
        assert "vision" in data


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/retry_task/{task_id}
# ──────────────────────────────────────────────────────────────────────────────

class TestRetryTask:
    def test_retry_unknown_task_404(self, client2):
        with mock.patch(
            "ollama_arena.arena.Arena.retry_task",
            side_effect=ValueError("task not found"),
        ):
            r = client2.post("/api/retry_task/no_such_id")
        assert r.status_code == 404

    def test_retry_known_task_200(self, client2):
        with mock.patch(
            "ollama_arena.arena.Arena.retry_task",
            return_value={"status": "ok", "score_a": 1.0, "score_b": 0.0},
        ):
            r = client2.post("/api/retry_task/task_abc")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/export_match/{match_id} and /api/export_royale/{royale_id}
# ──────────────────────────────────────────────────────────────────────────────

class TestExportMatchRoyale:
    def test_export_match_not_found_404(self, client2):
        r = client2.get("/api/export_match/999999")
        assert r.status_code == 404

    def test_export_royale_not_found_404(self, client2):
        r = client2.get("/api/export_royale/999999")
        assert r.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/strategy
# ──────────────────────────────────────────────────────────────────────────────

class TestStrategy:
    def test_strategy_missing_models_400(self, client2):
        r = client2.post("/api/strategy", json={})
        assert r.status_code == 400

    def test_strategy_missing_model_b_400(self, client2):
        r = client2.post("/api/strategy", json={"model_a": "llama3"})
        assert r.status_code == 400

    def test_strategy_with_models_200(self, client2):
        from ollama_arena.memory_scheduler import StrategyDecision, Strategy
        decision = StrategyDecision(
            strategy=Strategy.CONCURRENT,
            available_gb=8.0,
            model_a_gb=3.5,
            model_b_gb=2.5,
            reason="Both models fit in RAM",
        )
        with (
            mock.patch("ollama_arena.memory_scheduler.MemoryScheduler.choose", return_value=decision),
            mock.patch("ollama_arena.memory_scheduler.MemoryScheduler.total_ram_gb", return_value=16.0),
            mock.patch("ollama_arena.memory_scheduler.MemoryScheduler.usable_ram_gb", return_value=14.0),
            mock.patch("ollama_arena.memory_scheduler.MemoryScheduler.loaded_models_gb", return_value=2.0),
        ):
            r = client2.post("/api/strategy", json={"model_a": "llama3", "model_b": "phi3"})
        assert r.status_code == 200
        data = r.json()
        assert "strategy" in data
        assert data["strategy"] == "CONCURRENT"

    def test_strategy_response_has_ram_fields(self, client2):
        from ollama_arena.memory_scheduler import StrategyDecision, Strategy
        decision = StrategyDecision(
            strategy=Strategy.HOT_SWAP,
            available_gb=4.0,
            model_a_gb=3.0,
            model_b_gb=3.0,
            reason="Not enough RAM for both",
        )
        with (
            mock.patch("ollama_arena.memory_scheduler.MemoryScheduler.choose", return_value=decision),
            mock.patch("ollama_arena.memory_scheduler.MemoryScheduler.total_ram_gb", return_value=8.0),
            mock.patch("ollama_arena.memory_scheduler.MemoryScheduler.usable_ram_gb", return_value=6.0),
            mock.patch("ollama_arena.memory_scheduler.MemoryScheduler.loaded_models_gb", return_value=2.0),
        ):
            data = client2.post("/api/strategy", json={"model_a": "a", "model_b": "b"}).json()
        assert "total_ram_gb" in data
        assert "usable_ram_gb" in data
        assert "loaded_gb" in data


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/match
# ──────────────────────────────────────────────────────────────────────────────

class TestMatchEndpoint:
    def test_match_missing_models_400(self, client2):
        r = client2.post("/api/match", json={})
        assert r.status_code == 400

    def test_match_missing_model_b_400(self, client2):
        r = client2.post("/api/match", json={"model_a": "llama3"})
        assert r.status_code == 400

    def test_match_returns_job_id(self, client2):
        with mock.patch("ollama_arena.arena.Arena.run_match", side_effect=RuntimeError("no ollama")):
            r = client2.post("/api/match", json={"model_a": "llama3", "model_b": "phi3"})
        assert r.status_code == 200
        data = r.json()
        assert "job_id" in data
        assert isinstance(data["job_id"], str)

    def test_job_status_after_match(self, client2):
        with mock.patch("ollama_arena.arena.Arena.run_match", side_effect=RuntimeError("no ollama")):
            r = client2.post("/api/match", json={"model_a": "llama3", "model_b": "phi3"})
        job_id = r.json()["job_id"]
        status_r = client2.get(f"/api/job/{job_id}")
        assert status_r.status_code == 200
        data = status_r.json()
        # Job was created, even if background task errored
        assert data.get("status") in ("running", "done", "error")

    def test_job_unknown_id(self, client2):
        r = client2.get("/api/job/nonexistent-job-id-xyz")
        assert r.status_code == 200
        assert r.json()["status"] == "not_found"


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/tournament
# ──────────────────────────────────────────────────────────────────────────────

class TestTournamentEndpoint:
    def test_tournament_too_few_models_400(self, client2):
        r = client2.post("/api/tournament", json={"models": ["llama3"]})
        assert r.status_code == 400

    def test_tournament_returns_job_id(self, client2):
        with mock.patch("ollama_arena.arena.Arena.run_match", side_effect=RuntimeError("no ollama")):
            r = client2.post("/api/tournament", json={
                "models": ["llama3", "phi3"], "category": "coding", "n": 1
            })
        assert r.status_code == 200
        assert "job_id" in r.json()

    def test_tournament_empty_models_400(self, client2):
        r = client2.post("/api/tournament", json={"models": []})
        assert r.status_code == 400


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/royale
# ──────────────────────────────────────────────────────────────────────────────

class TestRoyaleEndpoint:
    def test_royale_too_few_models_400(self, client2):
        r = client2.post("/api/royale", json={"models": ["a", "b"]})
        assert r.status_code == 400

    def test_royale_returns_job_id(self, client2):
        with mock.patch("ollama_arena.arena.Arena.run_royale", side_effect=RuntimeError("no ollama")):
            r = client2.post("/api/royale", json={
                "models": ["llama3", "phi3", "mistral"], "category": "coding", "n": 1
            })
        assert r.status_code == 200
        assert "job_id" in r.json()

    def test_royale_one_model_400(self, client2):
        r = client2.post("/api/royale", json={"models": ["only_one"]})
        assert r.status_code == 400


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/playground/generate_single
# ──────────────────────────────────────────────────────────────────────────────

class TestPlaygroundGenerateSingle:
    def test_missing_model_400(self, client2):
        r = client2.post("/api/playground/generate_single", json={"prompt": "hello"})
        assert r.status_code == 400

    def test_missing_prompt_400(self, client2):
        r = client2.post("/api/playground/generate_single", json={"model": "llama3"})
        assert r.status_code == 400

    def test_generate_single_200(self, client2):
        gen = _mock_gen_result(text="The sky is blue.")
        with (
            mock.patch("ollama_arena.backends.ollama.OllamaBackend.generate", return_value=gen),
            mock.patch("ollama_arena.arena.Arena._log_perf"),
        ):
            r = client2.post("/api/playground/generate_single", json={
                "model": "llama3", "prompt": "Why is the sky blue?"
            })
        assert r.status_code == 200
        data = r.json()
        assert data["model"] == "llama3"
        assert "response" in data
        assert data["response"] == "The sky is blue."

    def test_generate_single_returns_tps(self, client2):
        gen = _mock_gen_result(text="answer", tps=25.0)
        with (
            mock.patch("ollama_arena.backends.ollama.OllamaBackend.generate", return_value=gen),
            mock.patch("ollama_arena.arena.Arena._log_perf"),
        ):
            data = client2.post("/api/playground/generate_single", json={
                "model": "phi3", "prompt": "test"
            }).json()
        assert "tps" in data


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/playground/generate
# ──────────────────────────────────────────────────────────────────────────────

class TestPlaygroundGenerate:
    def test_missing_models_400(self, client2):
        r = client2.post("/api/playground/generate", json={"prompt": "hello"})
        assert r.status_code == 400

    def test_missing_prompt_400(self, client2):
        r = client2.post("/api/playground/generate", json={
            "model_a": "llama3", "model_b": "phi3"
        })
        assert r.status_code == 400

    def test_generate_200(self, client2):
        gen_a = _mock_gen_result(text="Response A")
        gen_b = _mock_gen_result(text="Response B")
        call_count = {"n": 0}

        def _gen_side_effect(model, prompt, **_kw):
            call_count["n"] += 1
            return gen_a if call_count["n"] == 1 else gen_b

        with (
            mock.patch("ollama_arena.backends.ollama.OllamaBackend.generate", side_effect=_gen_side_effect),
            mock.patch("ollama_arena.arena.Arena._log_perf"),
        ):
            r = client2.post("/api/playground/generate", json={
                "model_a": "llama3", "model_b": "phi3", "prompt": "Tell me something"
            })
        assert r.status_code == 200
        data = r.json()
        assert "response_x" in data
        assert "response_y" in data
        assert "model_x" in data
        assert "model_y" in data

    def test_generate_returns_tps_fields(self, client2):
        gen = _mock_gen_result(tps=15.0)
        with (
            mock.patch("ollama_arena.backends.ollama.OllamaBackend.generate", return_value=gen),
            mock.patch("ollama_arena.arena.Arena._log_perf"),
        ):
            data = client2.post("/api/playground/generate", json={
                "model_a": "a", "model_b": "b", "prompt": "p"
            }).json()
        assert "tps_x" in data
        assert "tps_y" in data


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/playground/vote
# ──────────────────────────────────────────────────────────────────────────────

class TestPlaygroundVote:
    def test_vote_missing_params_400(self, client2):
        r = client2.post("/api/playground/vote", json={})
        assert r.status_code == 400

    def test_vote_missing_voted_for_400(self, client2):
        r = client2.post("/api/playground/vote", json={
            "model_a_name": "llama3", "model_b_name": "phi3",
            "model_x": "model_a",
        })
        assert r.status_code == 400

    def test_vote_x_wins_200(self, client2):
        r = client2.post("/api/playground/vote", json={
            "model_a_name": "llama3",
            "model_b_name": "phi3",
            "voted_for": "x",
            "model_x": "model_a",
            "model_y": "model_b",
            "prompt": "test prompt",
            "response_x": "resp A",
            "response_y": "resp B",
            "tps_x": 10.0,
            "tps_y": 8.0,
            "latency_x": 0.1,
            "latency_y": 0.2,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "recorded"

    def test_vote_draw_200(self, client2):
        r = client2.post("/api/playground/vote", json={
            "model_a_name": "llama3",
            "model_b_name": "phi3",
            "voted_for": "draw",
            "model_x": "model_a",
            "model_y": "model_b",
            "prompt": "q",
            "response_x": "r1",
            "response_y": "r2",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "recorded"

    def test_vote_y_wins_200(self, client2):
        r = client2.post("/api/playground/vote", json={
            "model_a_name": "llama3",
            "model_b_name": "phi3",
            "voted_for": "y",
            "model_x": "model_a",
            "model_y": "model_b",
            "prompt": "q",
            "response_x": "r1",
            "response_y": "r2",
        })
        assert r.status_code == 200


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/pull_dataset
# ──────────────────────────────────────────────────────────────────────────────

class TestPullDataset:
    def test_pull_missing_name_400(self, client2):
        r = client2.post("/api/pull_dataset", json={})
        assert r.status_code == 400

    def test_pull_with_name_200(self, client2):
        with mock.patch("ollama_arena.arena.Arena.load_hf_dataset"):
            r = client2.post("/api/pull_dataset", json={"name": "openai/gsm8k", "limit": 10})
        assert r.status_code == 200
        data = r.json()
        assert data["started"] is True
        assert data["name"] == "openai/gsm8k"


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/spec/servers
# ──────────────────────────────────────────────────────────────────────────────

class TestSpecEndpoints:
    def test_spec_servers_200(self, client2):
        r = client2.get("/api/spec/servers")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_spec_stop_all_200(self, client2):
        r = client2.post("/api/spec/stop_all")
        assert r.status_code == 200

    def test_spec_start_all_200(self, client2):
        r = client2.post("/api/spec/start_all")
        assert r.status_code == 200

    def test_spec_start_unknown_name_404_not_500(self, client2):
        """Unknown spec model name is a client error (404), not a server
        error (500) — start() returning ok=False for a bad name should not
        be conflated with an actual launch failure."""
        r = client2.post("/api/spec/start/not-a-real-spec-model")
        assert r.status_code == 404

    def test_spec_stop_unknown_name_404(self, client2):
        r = client2.post("/api/spec/stop/not-a-real-spec-model")
        assert r.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# /api/spec/start_all overlap guard — resource-exhaustion safeguard
# ──────────────────────────────────────────────────────────────────────────────

class TestSpecStartAllOverlapGuard:
    """A start_all sweep launches up to len(SPEC_SERVERS) real subprocess
    calls sequentially (each waits up to 30s for its port to open). Without
    a guard, a second overlapping call — e.g. once the 1/minute rate limit
    window resets, or always if slowapi isn't installed (the limiter becomes
    a no-op) — could pile a second full sweep on top of the first, racing on
    shared SpecManager state and multiplying real subprocess launches with no
    cap. This test verifies the in-process lock rejects a genuinely
    overlapping call with 409 instead of starting a second sweep.

    Mocks SpecManager.start (not subprocess.Popen) per the project's testing
    guidance — this must not weaken the conftest Popen-spawn guard.
    """

    def test_concurrent_start_all_rejects_second_call(self):
        import threading
        import time as _time
        import ollama_arena.web as _web_mod

        with mock.patch("slowapi.Limiter.limit", return_value=lambda fn: fn):
            with (
                mock.patch("uvicorn.run", side_effect=lambda app, **_kw: _captured.update(app=app)),
                mock.patch(
                    "ollama_arena.backends.ollama.OllamaBackend.list_models",
                    return_value=["llama3"],
                ),
            ):
                _captured: dict = {}
                from ollama_arena.web import run_web
                run_web(host="127.0.0.1", port=0, db_path=":memory:")
            app = _captured["app"]

        from starlette.testclient import TestClient
        local_client = TestClient(app, raise_server_exceptions=False)

        def _slow_start(name):
            _time.sleep(0.5)
            return {"ok": True}

        results: dict = {}

        def _call_first():
            results["first"] = local_client.post("/api/spec/start_all")

        with mock.patch(
            "ollama_arena.backends.spec.SpecManager.start", side_effect=_slow_start
        ):
            t = threading.Thread(target=_call_first)
            t.start()
            _time.sleep(0.1)  # let the first sweep start and acquire the flag
            overlap_response = local_client.post("/api/spec/start_all")
            t.join(timeout=10)

        assert results["first"].status_code == 200
        assert overlap_response.status_code == 409

    def test_start_all_succeeds_again_after_sweep_completes(self):
        """The guard must release after the sweep finishes — not permanently
        latch — so a legitimate follow-up call still succeeds."""
        import ollama_arena.web as _web_mod

        with mock.patch("slowapi.Limiter.limit", return_value=lambda fn: fn):
            with (
                mock.patch("uvicorn.run", side_effect=lambda app, **_kw: _captured.update(app=app)),
                mock.patch(
                    "ollama_arena.backends.ollama.OllamaBackend.list_models",
                    return_value=["llama3"],
                ),
            ):
                _captured: dict = {}
                from ollama_arena.web import run_web
                run_web(host="127.0.0.1", port=0, db_path=":memory:")
            app = _captured["app"]

        from starlette.testclient import TestClient
        local_client = TestClient(app, raise_server_exceptions=False)

        with mock.patch(
            "ollama_arena.backends.spec.SpecManager.start", return_value={"ok": True}
        ):
            r1 = local_client.post("/api/spec/start_all")
            r2 = local_client.post("/api/spec/start_all")
        assert r1.status_code == 200
        assert r2.status_code == 200


# ──────────────────────────────────────────────────────────────────────────────
# Numeric request-body validation — bad input must 400, not 500
# ──────────────────────────────────────────────────────────────────────────────

class TestNumericBodyValidation:
    """int(body.get(...)) / float(body.get(...)) on unvalidated user input
    used to raise an unhandled ValueError -> raw FastAPI 500 on plausible
    bad input (e.g. a buggy client sending a string where a number is
    expected). These now go through _body_num, which raises a clean
    HTTPException(400, ...) instead."""

    def test_match_non_numeric_n_returns_400(self, client2):
        r = client2.post("/api/match", json={
            "model_a": "a", "model_b": "b", "n": "not-a-number",
        })
        assert r.status_code == 400

    def test_match_non_numeric_concurrency_returns_400(self, client2):
        r = client2.post("/api/match", json={
            "model_a": "a", "model_b": "b", "concurrency": "lots",
        })
        assert r.status_code == 400

    def test_tournament_non_numeric_n_returns_400(self, client2):
        r = client2.post("/api/tournament", json={
            "models": ["a", "b"], "n": "abc",
        })
        assert r.status_code == 400

    def test_tournament_models_not_a_list_returns_400(self, client2):
        """A string happens to satisfy len(models) >= 2 character-wise —
        must be rejected as a type error, not silently iterated as chars."""
        r = client2.post("/api/tournament", json={"models": "ab"})
        assert r.status_code == 400

    def test_royale_non_numeric_n_returns_400(self, client2):
        r = client2.post("/api/royale", json={
            "models": ["a", "b", "c"], "n": "xyz",
        })
        assert r.status_code == 400

    def test_royale_models_not_a_list_returns_400(self, client2):
        r = client2.post("/api/royale", json={"models": "abc"})
        assert r.status_code == 400

    def test_playground_vote_non_numeric_tps_returns_400(self, client2):
        r = client2.post("/api/playground/vote", json={
            "model_a_name": "a", "model_b_name": "b",
            "voted_for": "x", "model_x": "model_a", "model_y": "model_b",
            "prompt": "p", "response_x": "rx", "response_y": "ry",
            "tps_x": "fast",
        })
        assert r.status_code == 400

    def test_spec_bench_all_non_numeric_max_tokens_returns_400(self, client2):
        r = client2.post("/api/spec/bench_all", json={"max_tokens": "lots"})
        assert r.status_code == 400

    def test_spec_vs_base_non_numeric_max_tokens_returns_400(self, client2):
        r = client2.post("/api/spec/vs_base", json={
            "model": "spec:qwen3-14b", "max_tokens": "lots",
        })
        assert r.status_code == 400


# ──────────────────────────────────────────────────────────────────────────────
# /api/strategy — non-string model fields must not crash with AttributeError
# ──────────────────────────────────────────────────────────────────────────────

class TestStrategyTypeSafety:
    """body.get("model_a", "").strip() raised AttributeError (-> raw 500)
    whenever model_a/model_b were present but not a string (e.g. null or a
    number) — the default only applies when the key is *missing*, not when
    it's present with a non-string value. Now coerced via str(... or "")."""

    def test_strategy_null_model_a_returns_400_not_500(self, client2):
        r = client2.post("/api/strategy", json={"model_a": None, "model_b": "b"})
        assert r.status_code == 400

    def test_strategy_non_string_model_a_does_not_500(self, client2):
        """A non-string-but-truthy value (e.g. a number) is coerced via
        str() and proceeds normally — it must not crash with AttributeError
        from a bare .strip() call on a non-str."""
        r = client2.post("/api/strategy", json={"model_a": 123, "model_b": "b"})
        assert r.status_code != 500


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/genome/scan — progress broadcast must actually fire
# ──────────────────────────────────────────────────────────────────────────────

class TestGenomeScanBroadcast:
    """_do_scan() runs via BackgroundTasks in a worker thread that has no
    running event loop of its own. The old code called
    asyncio.get_event_loop() from inside that thread, which raises (silently
    swallowed by a bare except) — so loop.is_running() was never reached and
    manager.broadcast() never actually ran; only the polling endpoint
    (/api/genome/scan/progress) reflected progress. The fix captures the
    request's running loop up front and uses run_coroutine_threadsafe to
    hand events back to it. This test verifies the broadcast callback is
    genuinely invoked (not just that the route returns 200)."""

    def test_genome_scan_triggers_broadcast(self, client2):
        """Connect a real WebSocket client (the same path real dashboard
        clients use) and assert it actually receives a genome_scan_progress
        event when a scan runs — proving the broadcast fires end-to-end
        rather than silently failing inside the background-task thread."""
        pytest.importorskip("ollama_arena.genome.scanner")

        def _fake_scan_local(on_progress=None):
            if on_progress:
                on_progress(1, 1, "fake-model")
            return []

        with client2.websocket_connect("/ws") as ws:
            with mock.patch(
                "ollama_arena.genome.scanner.OllamaScanner.scan_local",
                side_effect=_fake_scan_local,
            ):
                r = client2.post("/api/genome/scan")
                assert r.status_code == 200
                msg = ws.receive_json()

        assert msg.get("type") == "genome_scan_progress"
        assert msg.get("model") == "fake-model"
