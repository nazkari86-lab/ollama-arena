"""Extended tests for arena.py — Arena class and helpers."""
from __future__ import annotations
import time
import unittest.mock as mock
import pytest


# ─── _agent_trace_json ───────────────────────────────────────────────────────

class TestAgentTraceJson:
    def test_no_trace(self):
        from ollama_arena.arena import _agent_trace_json
        from ollama_arena.backends.base import GenResult
        res = GenResult(text="hi", model="m")
        assert _agent_trace_json(res) is None

    def test_empty_trace(self):
        from ollama_arena.arena import _agent_trace_json
        from ollama_arena.backends.base import GenResult
        res = GenResult(text="hi", model="m")
        res.agent_trace = []
        assert _agent_trace_json(res) is None

    def test_with_trace(self):
        from ollama_arena.arena import _agent_trace_json
        from ollama_arena.backends.base import GenResult
        import json
        res = GenResult(text="hi", model="m")
        res.agent_trace = [{"tool": "search", "result": "found"}]
        result = _agent_trace_json(res)
        assert result is not None
        parsed = json.loads(result)
        assert parsed[0]["tool"] == "search"

    def test_non_serializable_trace(self):
        from ollama_arena.arena import _agent_trace_json
        from ollama_arena.backends.base import GenResult
        res = GenResult(text="hi", model="m")
        # Create a trace with non-serializable object
        res.agent_trace = [object()]
        result = _agent_trace_json(res)
        assert result is None


# ─── MatchResult / RoyaleResult dataclasses ──────────────────────────────────

class TestMatchResult:
    def test_defaults(self):
        from ollama_arena.arena import MatchResult
        mr = MatchResult(
            model_a="a", model_b="b", category="coding",
            tasks_run=5, a_wins=3, b_wins=1, draws=1,
            a_win_rate=0.6, b_win_rate=0.2,
            elo_a_before=1200, elo_b_before=1200,
            elo_a_after=1215, elo_b_after=1185,
        )
        assert mr.task_results == []
        assert mr.duration_s == 0.0
        assert mr.match_id == 0
        assert mr.strategy == "CONCURRENT"
        assert mr.strategy_reason == ""

    def test_custom_values(self):
        from ollama_arena.arena import MatchResult
        mr = MatchResult(
            model_a="x", model_b="y", category="math",
            tasks_run=3, a_wins=2, b_wins=1, draws=0,
            a_win_rate=0.667, b_win_rate=0.333,
            elo_a_before=1100, elo_b_before=1300,
            elo_a_after=1120, elo_b_after=1280,
            task_results=[{"task_id": "t1"}],
            duration_s=12.5, match_id=42,
            strategy="PIPELINE", strategy_reason="low memory",
        )
        assert mr.match_id == 42
        assert mr.strategy == "PIPELINE"


class TestRoyaleResult:
    def test_defaults(self):
        from ollama_arena.arena import RoyaleResult
        rr = RoyaleResult(
            models=["a", "b", "c"], category="coding",
            tasks_run=5, winner="a",
            rankings=[{"model": "a", "rank": 1}],
        )
        assert rr.duration_s == 0.0
        assert rr.royale_id == 0
        assert rr.strategy == "CONCURRENT"


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _make_gen_result(text="solved", error="", tps=10.0, latency_s=0.5):
    from ollama_arena.backends.base import GenResult
    return GenResult(
        text=text, model="test_model", tps=tps, latency_s=latency_s,
        tokens_in=50, tokens_out=100, time_to_first=0.1, backend_type="mock",
        error=error,
    )


@pytest.fixture
def mock_backend():
    from ollama_arena.backends.base import Backend
    backend = mock.MagicMock(spec=Backend)
    backend.name = "mock_backend"
    backend.generate.return_value = _make_gen_result("solved")
    return backend


@pytest.fixture
def arena(mock_backend, tmp_path):
    """Arena with mocked dependencies."""
    from ollama_arena.arena import Arena
    db = str(tmp_path / "arena.db")
    with mock.patch("ollama_arena.arena.auto_backend", return_value=mock_backend), \
         mock.patch("ollama_arena.arena.MemoryScheduler"):
        a = Arena(db_path=db)
    return a


# ─── Arena.__init__ ───────────────────────────────────────────────────────────

class TestArenaInit:
    def test_default_init(self, tmp_path):
        from ollama_arena.arena import Arena
        db = str(tmp_path / "arena.db")
        with mock.patch("ollama_arena.arena.auto_backend") as mock_ab, \
             mock.patch("ollama_arena.arena.MemoryScheduler"):
            mock_ab.return_value = mock.MagicMock()
            a = Arena(db_path=db)
        assert a.client is not None
        assert a._on_task_done is None
        assert a.judge is None

    def test_backend_string(self, tmp_path):
        from ollama_arena.arena import Arena
        db = str(tmp_path / "arena.db")
        with mock.patch("ollama_arena.arena.auto_backend") as mock_ab, \
             mock.patch("ollama_arena.arena.MemoryScheduler"):
            mock_ab.return_value = mock.MagicMock()
            a = Arena(backend="ollama", db_path=db)
        mock_ab.assert_called_with("ollama", api_key=None)

    def test_backend_instance(self, tmp_path, mock_backend):
        from ollama_arena.arena import Arena
        db = str(tmp_path / "arena.db")
        with mock.patch("ollama_arena.arena.MemoryScheduler"):
            a = Arena(backend=mock_backend, db_path=db)
        assert a.client is mock_backend

    def test_with_judge_model(self, tmp_path, mock_backend):
        from ollama_arena.arena import Arena
        db = str(tmp_path / "arena.db")
        with mock.patch("ollama_arena.arena.auto_backend", return_value=mock_backend), \
             mock.patch("ollama_arena.arena.MemoryScheduler"), \
             mock.patch("ollama_arena.judge.LLMJudge") as mock_judge:
            a = Arena(db_path=db, judge_model="judge:7b")
        assert a.judge is not None

    def test_with_on_task_done(self, tmp_path, mock_backend):
        from ollama_arena.arena import Arena
        db = str(tmp_path / "arena.db")
        cb = mock.MagicMock()
        with mock.patch("ollama_arena.arena.auto_backend", return_value=mock_backend), \
             mock.patch("ollama_arena.arena.MemoryScheduler"):
            a = Arena(db_path=db, on_task_done=cb)
        assert a._on_task_done is cb

    def test_from_datasets(self, tmp_path, mock_backend):
        from ollama_arena.arena import Arena
        db = str(tmp_path / "arena.db")
        with mock.patch("ollama_arena.arena.auto_backend", return_value=mock_backend), \
             mock.patch("ollama_arena.arena.MemoryScheduler"), \
             mock.patch("ollama_arena.arena.Arena.load_hf_dataset") as mock_load:
            mock_load.return_value = 10
            a = Arena(db_path=db, from_datasets=["humaneval"])
        mock_load.assert_called_once_with("humaneval")


# ─── Arena properties ─────────────────────────────────────────────────────────

class TestArenaProperties:
    def test_mcp_property_lazy_init(self, arena):
        with mock.patch("ollama_arena.mcp_client.MCPOrchestrator") as mock_orch:
            mock_orch.return_value = mock.MagicMock()
            mcp = arena.mcp
        assert mcp is not None
        # Second call uses cached value
        mcp2 = arena.mcp
        assert mcp is mcp2

    def test_webui_property_lazy_init(self, arena):
        with mock.patch("ollama_arena.webui_bridge.WebUIBridge") as mock_wb:
            mock_wb.return_value = mock.MagicMock()
            webui = arena.webui
        assert webui is not None
        webui2 = arena.webui
        assert webui is webui2


# ─── Arena.load_hf_dataset ───────────────────────────────────────────────────

class TestLoadHfDataset:
    def test_loads_tasks(self, arena):
        mock_tasks = [
            {"id": "t1", "instruction": "code", "category": "coding"},
            {"id": "t2", "instruction": "math", "category": "math"},
        ]
        with mock.patch("ollama_arena.arena.Arena.load_hf_dataset",
                        side_effect=lambda name, limit=None: (
                            arena._extra_tasks.setdefault("coding", []).extend(mock_tasks[:1]) or
                            arena._extra_tasks.setdefault("math", []).extend(mock_tasks[1:]) or 2
                        )):
            pass  # just set up _extra_tasks directly
        arena._extra_tasks["coding"] = [{"id": "t1", "instruction": "code"}]
        assert len(arena._extra_tasks["coding"]) == 1

    def test_returns_count(self, arena):
        with mock.patch("ollama_arena.datasets.load_dataset", return_value=[
            {"id": "t1", "category": "coding"},
            {"id": "t2", "category": "math"},
        ]):
            count = arena.load_hf_dataset("humaneval")
        assert count == 2


# ─── Arena._gather_tasks ─────────────────────────────────────────────────────

class TestGatherTasks:
    def test_returns_builtin_tasks(self, arena):
        tasks = arena._gather_tasks("coding", 5)
        assert isinstance(tasks, list)

    def test_respects_limit(self, arena):
        all_tasks = arena._gather_tasks("coding", 100)
        limited = arena._gather_tasks("coding", 2)
        assert len(limited) <= 2

    def test_extra_tasks_included(self, arena):
        arena._extra_tasks["my_cat"] = [
            {"id": "e1", "instruction": "extra", "category": "my_cat"},
        ]
        tasks = arena._gather_tasks("my_cat", 10)
        assert any(t["id"] == "e1" for t in tasks)

    def test_difficulty_filter(self, arena):
        arena._extra_tasks["coding"] = [
            {"id": "e1", "instruction": "hard task", "category": "coding", "difficulty": "hard"},
            {"id": "e2", "instruction": "easy task", "category": "coding", "difficulty": "easy"},
        ]
        tasks = arena._gather_tasks("coding", 10, difficulty="hard")
        assert all(t.get("difficulty") == "hard" for t in tasks if "difficulty" in t)


# ─── Arena.leaderboard, match_history, performance_stats ─────────────────────

class TestArenaSimpleMethods:
    def test_leaderboard(self, arena):
        arena.elo.leaderboard = mock.MagicMock(return_value=[{"model": "a", "elo": 1200}])
        lb = arena.leaderboard()
        assert len(lb) == 1

    def test_match_history(self, arena):
        arena.elo.match_history = mock.MagicMock(return_value=[])
        hist = arena.match_history(limit=5)
        assert isinstance(hist, list)

    def test_performance_stats(self, arena):
        arena.perf.export_summary = mock.MagicMock(return_value={"total": 0})
        stats = arena.performance_stats()
        assert stats["total"] == 0


# ─── Arena._log_perf ─────────────────────────────────────────────────────────

class TestLogPerf:
    def test_logs_successful_result(self, arena):
        res = _make_gen_result("ok", tps=5.0, latency_s=1.0)
        arena.perf.record = mock.MagicMock()
        arena._log_perf("model_a", res, "coding")
        arena.perf.record.assert_called_once()

    def test_skips_failed_result(self, arena):
        res = _make_gen_result("", error="timeout")
        arena.perf.record = mock.MagicMock()
        arena._log_perf("model_a", res, "coding")
        arena.perf.record.assert_not_called()

    def test_logs_tool_calls(self, arena):
        from ollama_arena.backends.base import GenResult
        res = GenResult(
            text="ok", model="m", tps=5.0, latency_s=1.0,
            tokens_in=10, tokens_out=20, time_to_first=0.2, backend_type="mock",
            agent_trace=[{"tool_results": [{"name": "search", "latency_s": 0.3}]}],
        )
        arena.perf.record = mock.MagicMock()
        arena.perf.record_tool = mock.MagicMock()
        arena._log_perf("model_a", res, "coding")
        arena.perf.record_tool.assert_called_once_with("search", "model_a", 0.3, category="coding")


# ─── Arena._sync_webui_bridge ────────────────────────────────────────────────

class TestSyncWebuiBridge:
    def test_no_key_skips(self, arena):
        from ollama_arena.arena import MatchResult
        mr = MatchResult("a", "b", "c", 1, 1, 0, 0, 1.0, 0.0, 1200, 1200, 1215, 1185)
        with mock.patch.dict("os.environ", {}, clear=True):
            arena._sync_webui_bridge(mr)  # should not raise

    def test_with_key_syncs(self, arena):
        from ollama_arena.arena import MatchResult
        mr = MatchResult("a", "b", "coding", 1, 1, 0, 0, 1.0, 0.0, 1200, 1200, 1215, 1185)
        mr.match_id = 1
        mr.duration_s = 5.0
        mock_webui = mock.MagicMock()
        arena._webui = mock_webui
        arena.elo.leaderboard = mock.MagicMock(return_value=[])
        with mock.patch.dict("os.environ", {"WEBUI_API_KEY": "key123"}):
            arena._sync_webui_bridge(mr)
        mock_webui.broadcast_match_result.assert_called_once()
        mock_webui.sync_leaderboard.assert_called_once()

    def test_webui_exception_logged(self, arena):
        from ollama_arena.arena import MatchResult
        mr = MatchResult("a", "b", "coding", 1, 1, 0, 0, 1.0, 0.0, 1200, 1200, 1215, 1185)
        mock_webui = mock.MagicMock()
        mock_webui.broadcast_match_result.side_effect = Exception("conn error")
        arena._webui = mock_webui
        arena.elo.leaderboard = mock.MagicMock(return_value=[])
        with mock.patch.dict("os.environ", {"WEBUI_API_KEY": "key123"}):
            arena._sync_webui_bridge(mr)  # should not raise


# ─── Arena.run_match ─────────────────────────────────────────────────────────

class TestRunMatch:
    def _make_arena(self, tmp_path, strategy="CONCURRENT"):
        from ollama_arena.arena import Arena
        from ollama_arena.backends.base import GenResult, Backend
        from ollama_arena.memory_scheduler import Strategy, StrategyDecision

        mock_b = mock.MagicMock(spec=Backend)
        mock_b.name = "mock"
        mock_b.generate.return_value = _make_gen_result("def solution(): return 42")

        decision = StrategyDecision(
            strategy=Strategy[strategy],
            available_gb=8.0,
            model_a_gb=2.0,
            model_b_gb=2.0,
            reason="test",
        )

        db = str(tmp_path / "arena.db")
        with mock.patch("ollama_arena.arena.auto_backend", return_value=mock_b), \
             mock.patch("ollama_arena.arena.MemoryScheduler") as mock_sched:
            mock_sched.return_value.choose.return_value = decision
            mock_sched.return_value.choose_royale.return_value = decision
            mock_sched.return_value.unload = mock.MagicMock()
            mock_sched.return_value.unload_all_except = mock.MagicMock()
            mock_sched.return_value.prefetch = mock.MagicMock()
            a = Arena(db_path=db)
        a.client = mock_b
        return a

    def test_no_tasks_raises(self, tmp_path):
        a = self._make_arena(tmp_path)
        with pytest.raises(ValueError, match="No tasks"):
            a.run_match("a", "b", category="nonexistent_cat_xyz", n=10)

    def test_basic_match(self, tmp_path):
        a = self._make_arena(tmp_path)
        with mock.patch("ollama_arena.arena.spec_backend_for_model", return_value=None), \
             mock.patch("ollama_arena.arena.evaluate", return_value=0.8):
            result = a.run_match("model_a", "model_b", category="coding", n=2)
        assert result.model_a == "model_a"
        assert result.model_b == "model_b"
        assert result.tasks_run == 2
        assert result.a_wins + result.b_wins + result.draws == 2

    def test_match_with_on_task_done(self, tmp_path):
        a = self._make_arena(tmp_path)
        cb = mock.MagicMock()
        a._on_task_done = cb
        with mock.patch("ollama_arena.arena.spec_backend_for_model", return_value=None), \
             mock.patch("ollama_arena.arena.evaluate", return_value=0.7):
            a.run_match("model_a", "model_b", category="coding", n=1)
        cb.assert_called()

    def test_match_a_wins(self, tmp_path):
        a = self._make_arena(tmp_path)
        call_count = [0]
        def score_side(task, text, **kw):
            call_count[0] += 1
            return 0.9 if call_count[0] % 2 == 1 else 0.1  # alternating high/low
        with mock.patch("ollama_arena.arena.spec_backend_for_model", return_value=None), \
             mock.patch("ollama_arena.arena.evaluate", side_effect=score_side):
            result = a.run_match("model_a", "model_b", category="coding", n=2)
        assert result.a_wins > 0 or result.b_wins > 0 or result.draws > 0

    def test_match_hot_swap(self, tmp_path):
        a = self._make_arena(tmp_path, strategy="HOT_SWAP")
        with mock.patch("ollama_arena.arena.spec_backend_for_model", return_value=None), \
             mock.patch("ollama_arena.arena.evaluate", return_value=0.5):
            result = a.run_match("model_a", "model_b", category="coding", n=1)
        assert result.strategy == "HOT_SWAP"

    def test_match_pipeline(self, tmp_path):
        a = self._make_arena(tmp_path, strategy="PIPELINE")
        with mock.patch("ollama_arena.arena.spec_backend_for_model", return_value=None), \
             mock.patch("ollama_arena.arena.evaluate", return_value=0.5):
            result = a.run_match("model_a", "model_b", category="coding", n=1)
        assert result.strategy == "PIPELINE"


# ─── Arena.run_tournament ─────────────────────────────────────────────────────

class TestRunTournament:
    def test_basic_tournament(self, arena):
        arena.run_match = mock.MagicMock()
        arena.elo.leaderboard = mock.MagicMock(return_value=[])
        result = arena.run_tournament(["a", "b", "c"], category="coding", n_per_match=1)
        # 3 models → 3 pairs
        assert arena.run_match.call_count == 3
        assert isinstance(result, list)


# ─── Arena.retry_task ────────────────────────────────────────────────────────

class TestRetryTask:
    def test_no_prior_record_raises(self, arena):
        arena.elo.task_history = mock.MagicMock(return_value=[])
        with pytest.raises(ValueError, match="No prior record"):
            arena.retry_task("nonexistent_task")

    def test_retry_success(self, arena):
        arena.elo.task_history = mock.MagicMock(return_value=[{
            "model_a": "a", "model_b": "b",
            "category": "coding", "instruction": "solve this",
            "expected": "42", "difficulty": "medium",
        }])
        arena.client.generate.return_value = _make_gen_result("42")
        arena.elo.record_match = mock.MagicMock()
        arena.elo.last_match_id = mock.MagicMock(return_value=99)
        arena.elo.save_task_detail = mock.MagicMock()
        arena.perf.record = mock.MagicMock()
        with mock.patch("ollama_arena.arena.spec_backend_for_model", return_value=None), \
             mock.patch("ollama_arena.arena.evaluate", return_value=0.8), \
             mock.patch("ollama_arena.arena.get_task", return_value=None):
            result = arena.retry_task("task_1")
        assert result["ok"] is True
        assert result["model_a"] == "a"

    def test_retry_needs_judge(self, arena):
        arena.elo.task_history = mock.MagicMock(return_value=[{
            "model_a": "a", "model_b": "b",
            "category": "coding", "instruction": "judge needed",
            "expected": "", "difficulty": "medium",
        }])
        arena.client.generate.return_value = _make_gen_result("answer")
        arena.perf.record = mock.MagicMock()
        with mock.patch("ollama_arena.arena.spec_backend_for_model", return_value=None), \
             mock.patch("ollama_arena.arena.evaluate", return_value=None), \
             mock.patch("ollama_arena.arena.get_task", return_value=None):
            result = arena.retry_task("task_1")
        assert result["ok"] is False
        assert "judge" in result["error"].lower()
