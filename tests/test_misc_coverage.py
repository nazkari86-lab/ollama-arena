"""Coverage boost tests for smaller modules:
- finetune/analyzer.py
- finetune/ollama_export.py
- webui_bridge.py
- mcp/security.py
- visualize/charts.py (HTML generators)
"""
from __future__ import annotations

import os
import sqlite3
import unittest.mock as mock
import pytest


# ──────────────────────────────────────────────────────────────────────────────
# finetune/analyzer.py
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def analyzer_db(tmp_path):
    db = str(tmp_path / "analyzer.db")
    cx = sqlite3.connect(db)
    cx.executescript("""
        CREATE TABLE match_log (
            id INTEGER PRIMARY KEY,
            model_a TEXT, model_b TEXT, category TEXT,
            score_a REAL, score_b REAL,
            elo_a_before REAL DEFAULT 1200, elo_b_before REAL DEFAULT 1200,
            elo_a_after REAL DEFAULT 1200, elo_b_after REAL DEFAULT 1200,
            ts REAL DEFAULT 0
        );
        CREATE TABLE task_detail (
            id INTEGER PRIMARY KEY,
            match_id INTEGER, task_id TEXT, category TEXT,
            instruction TEXT, score_a REAL, score_b REAL, outcome TEXT,
            ts REAL DEFAULT 0
        );
    """)
    cx.commit()
    cx.close()
    return db


class TestAnalyzeWeaknesses:
    def test_empty_db_returns_empty(self, analyzer_db):
        from ollama_arena.finetune.analyzer import analyze_weaknesses
        result = analyze_weaknesses(analyzer_db)
        assert result == []

    def test_finds_weak_model(self, analyzer_db):
        from ollama_arena.finetune.analyzer import analyze_weaknesses
        cx = sqlite3.connect(analyzer_db)
        # model_a loses 3 times to model_b
        for i in range(3):
            cx.execute(
                "INSERT INTO match_log (model_a,model_b,category,score_a,score_b) "
                "VALUES ('loser','winner','coding',0.3,0.9)"
            )
        cx.commit()
        cx.close()
        result = analyze_weaknesses(analyzer_db, min_matches=3)
        models = [r["model"] for r in result]
        assert "loser" in models
        for r in result:
            if r["model"] == "loser":
                assert r["win_rate"] < 0.5

    def test_strong_model_excluded(self, analyzer_db):
        from ollama_arena.finetune.analyzer import analyze_weaknesses
        cx = sqlite3.connect(analyzer_db)
        for i in range(3):
            cx.execute(
                "INSERT INTO match_log (model_a,model_b,category,score_a,score_b) "
                "VALUES ('winner','loser','coding',0.9,0.3)"
            )
        cx.commit()
        cx.close()
        result = analyze_weaknesses(analyzer_db, min_matches=3)
        models = [r["model"] for r in result]
        assert "winner" not in models

    def test_below_min_matches_excluded(self, analyzer_db):
        from ollama_arena.finetune.analyzer import analyze_weaknesses
        cx = sqlite3.connect(analyzer_db)
        cx.execute("INSERT INTO match_log (model_a,model_b,category,score_a,score_b) VALUES ('a','b','math',0.1,0.9)")
        cx.commit()
        cx.close()
        result = analyze_weaknesses(analyzer_db, min_matches=3)
        assert result == []


class TestAnalyzeTaskFailures:
    def test_empty_returns_empty(self, analyzer_db):
        from ollama_arena.finetune.analyzer import analyze_task_failures
        result = analyze_task_failures(analyzer_db)
        assert result == []

    def test_finds_failures(self, analyzer_db):
        from ollama_arena.finetune.analyzer import analyze_task_failures
        cx = sqlite3.connect(analyzer_db)
        cx.execute(
            "INSERT INTO match_log (id,model_a,model_b,category,score_a,score_b) "
            "VALUES (1,'m_bad','m_good','coding',0.2,0.9)"
        )
        cx.execute(
            "INSERT INTO task_detail (match_id,task_id,category,instruction,score_a,score_b,outcome) "
            "VALUES (1,'t1','coding','write code',0.2,0.9,'b_wins')"
        )
        cx.commit()
        cx.close()
        result = analyze_task_failures(analyzer_db)
        assert len(result) >= 1

    def test_filter_by_model(self, analyzer_db):
        from ollama_arena.finetune.analyzer import analyze_task_failures
        cx = sqlite3.connect(analyzer_db)
        cx.execute(
            "INSERT INTO match_log (id,model_a,model_b,category,score_a,score_b) "
            "VALUES (1,'alpha','beta','math',0.1,0.9)"
        )
        cx.execute(
            "INSERT INTO task_detail (match_id,task_id,category,instruction,score_a,score_b,outcome) "
            "VALUES (1,'t1','math','question',0.1,0.9,'b_wins')"
        )
        cx.commit()
        cx.close()
        result_alpha = analyze_task_failures(analyzer_db, model="alpha")
        result_other = analyze_task_failures(analyzer_db, model="other_model")
        assert len(result_alpha) >= 1
        assert result_other == []

    def test_filter_by_category(self, analyzer_db):
        from ollama_arena.finetune.analyzer import analyze_task_failures
        cx = sqlite3.connect(analyzer_db)
        cx.execute(
            "INSERT INTO match_log (id,model_a,model_b,category,score_a,score_b) "
            "VALUES (1,'a','b','math',0.1,0.9)"
        )
        cx.execute(
            "INSERT INTO task_detail (match_id,task_id,category,instruction,score_a,score_b,outcome) "
            "VALUES (1,'t1','math','q',0.1,0.9,'b_wins')"
        )
        cx.commit()
        cx.close()
        result = analyze_task_failures(analyzer_db, category="math")
        assert len(result) >= 1
        result_other = analyze_task_failures(analyzer_db, category="coding")
        assert result_other == []


class TestWeaknessReport:
    def test_no_data_returns_no_candidates(self, analyzer_db):
        from ollama_arena.finetune.analyzer import weakness_report
        r = weakness_report(analyzer_db)
        assert "No fine-tuning" in r

    def test_with_weak_model_shows_table(self, analyzer_db):
        from ollama_arena.finetune.analyzer import weakness_report
        cx = sqlite3.connect(analyzer_db)
        for i in range(3):
            cx.execute(
                "INSERT INTO match_log (model_a,model_b,category,score_a,score_b) "
                "VALUES ('weak','strong','coding',0.2,0.9)"
            )
        cx.commit()
        cx.close()
        r = weakness_report(analyzer_db)
        assert "weak" in r
        assert "coding" in r


class TestTaskFailureReport:
    def test_no_failures_returns_no_record(self, analyzer_db):
        from ollama_arena.finetune.analyzer import task_failure_report
        r = task_failure_report(analyzer_db)
        assert "No task-level failures" in r

    def test_with_failures(self, analyzer_db):
        from ollama_arena.finetune.analyzer import task_failure_report
        cx = sqlite3.connect(analyzer_db)
        cx.execute(
            "INSERT INTO match_log (id,model_a,model_b,category,score_a,score_b) "
            "VALUES (1,'a','b','coding',0.1,0.9)"
        )
        cx.execute(
            "INSERT INTO task_detail (match_id,task_id,category,instruction,score_a,score_b,outcome) "
            "VALUES (1,'task_001','coding','instruction',0.1,0.9,'b_wins')"
        )
        cx.commit()
        cx.close()
        r = task_failure_report(analyzer_db)
        assert "task_001" in r


# ──────────────────────────────────────────────────────────────────────────────
# finetune/ollama_export.py
# ──────────────────────────────────────────────────────────────────────────────

class TestBuildModelfile:
    def test_creates_file(self, tmp_path):
        from ollama_arena.finetune.ollama_export import build_modelfile
        out = str(tmp_path / "Modelfile")
        result = build_modelfile("model.gguf", out)
        assert result == out
        content = open(out).read()
        assert "model.gguf" in content
        assert "num_ctx 4096" in content

    def test_contains_template(self, tmp_path):
        from ollama_arena.finetune.ollama_export import build_modelfile
        out = str(tmp_path / "Modelfile")
        build_modelfile("/path/to/model.gguf", out)
        content = open(out).read()
        assert "PARAMETER" in content


class TestInstallToOllama:
    def test_success(self, tmp_path):
        from ollama_arena.finetune.ollama_export import install_to_ollama
        mock_result = mock.MagicMock()
        mock_result.returncode = 0
        with mock.patch("subprocess.run", return_value=mock_result) as m:
            result = install_to_ollama("Modelfile", "my-model")
        assert result is True
        m.assert_called_once()

    def test_failure_returncode(self, tmp_path):
        from ollama_arena.finetune.ollama_export import install_to_ollama
        mock_result = mock.MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error message"
        with mock.patch("subprocess.run", return_value=mock_result):
            result = install_to_ollama("Modelfile", "my-model")
        assert result is False

    def test_exception_returns_false(self):
        from ollama_arena.finetune.ollama_export import install_to_ollama
        with mock.patch("subprocess.run", side_effect=FileNotFoundError("ollama not found")):
            result = install_to_ollama("Modelfile", "my-model")
        assert result is False


# ──────────────────────────────────────────────────────────────────────────────
# webui_bridge.py
# ──────────────────────────────────────────────────────────────────────────────

class TestWebUIBridge:
    def test_no_api_key_sync_returns_false(self):
        from ollama_arena.webui_bridge import WebUIBridge
        bridge = WebUIBridge(base_url="http://localhost:3000", api_key=None)
        # No API key → headers empty → sync returns False
        with mock.patch.dict(os.environ, {}, clear=True):
            # Remove WEBUI_API_KEY if set
            os.environ.pop("WEBUI_API_KEY", None)
            bridge2 = WebUIBridge(base_url="http://localhost:3000")
            result = bridge2.sync_leaderboard([{"model": "a", "elo": 1200, "rank": 1}])
        assert result is False

    def test_with_api_key_sync_returns_true(self):
        from ollama_arena.webui_bridge import WebUIBridge
        bridge = WebUIBridge(base_url="http://localhost:3000", api_key="test-key")
        leaderboard = [
            {"model": "phi-4", "elo": 1250.0, "rank": 1},
            {"model": "qwen", "elo": 1190.0, "rank": 2},
        ]
        result = bridge.sync_leaderboard(leaderboard)
        assert result is True

    def test_with_api_key_no_entries_returns_true(self):
        from ollama_arena.webui_bridge import WebUIBridge
        bridge = WebUIBridge(base_url="http://localhost:3000", api_key="test-key")
        result = bridge.sync_leaderboard([])
        assert result is True

    def test_broadcast_match_result_no_key(self):
        from ollama_arena.webui_bridge import WebUIBridge
        bridge = WebUIBridge(base_url="http://localhost:3000")
        # Should not raise, just return early
        bridge.broadcast_match_result("match completed")

    def test_broadcast_match_result_with_key(self):
        from ollama_arena.webui_bridge import WebUIBridge
        bridge = WebUIBridge(base_url="http://localhost:3000", api_key="test-key")
        # Should not raise
        bridge.broadcast_match_result("match completed")

    def test_api_key_from_env(self):
        from ollama_arena.webui_bridge import WebUIBridge
        with mock.patch.dict(os.environ, {"WEBUI_API_KEY": "env-key"}):
            bridge = WebUIBridge()
            assert "Authorization" in bridge._headers


# ──────────────────────────────────────────────────────────────────────────────
# mcp/security.py
# ──────────────────────────────────────────────────────────────────────────────

class TestCheckSecurityGateSafe:
    def test_safe_tier_always_allowed(self):
        from ollama_arena.mcp.security import check_security_gate
        allowed, msg = check_security_gate("read_file", {}, "safe")
        assert allowed is True
        assert msg == ""


class TestCheckSecurityGateDeny:
    def test_deny_with_auto_approve(self):
        from ollama_arena.mcp.security import check_security_gate
        with mock.patch.dict(os.environ, {
            "ARENA_AUTO_APPROVE": "1",
            "PYTEST_CURRENT_TEST": "",
        }):
            # PYTEST_CURRENT_TEST="" is falsy, so won't trigger early return
            # but we need to clear it to test the real deny path
            pass

        # Bypass PYTEST_CURRENT_TEST by removing it
        env = {k: v for k, v in os.environ.items() if k != "PYTEST_CURRENT_TEST"}
        env["ARENA_AUTO_APPROVE"] = "1"
        with mock.patch.dict(os.environ, env, clear=True):
            allowed, msg = check_security_gate("danger_tool", {}, "deny")
        assert allowed is True

    def test_deny_without_auto_approve(self):
        from ollama_arena.mcp.security import check_security_gate
        env = {k: v for k, v in os.environ.items() if k != "PYTEST_CURRENT_TEST"}
        env.pop("ARENA_AUTO_APPROVE", None)
        with mock.patch.dict(os.environ, env, clear=True):
            allowed, msg = check_security_gate("danger_tool", {}, "deny")
        assert allowed is False
        assert "danger_tool" in msg

    def test_deny_stays_denied_under_pytest_current_test(self):
        """Regression: PYTEST_CURRENT_TEST (set automatically by pytest itself,
        not opt-in) used to short-circuit check_security_gate to always-allow
        BEFORE the deny-tier check ran, meaning a permanently-denied tool would
        silently execute any time the orchestrator happened to run under pytest.
        The deny tier must win regardless of PYTEST_CURRENT_TEST; only explicit
        ARENA_AUTO_APPROVE=1 may override it."""
        from ollama_arena.mcp.security import check_security_gate
        env = dict(os.environ)
        env["PYTEST_CURRENT_TEST"] = "tests/whatever.py::test_x (call)"
        env.pop("ARENA_AUTO_APPROVE", None)
        with mock.patch.dict(os.environ, env, clear=True):
            allowed, msg = check_security_gate("danger_tool", {}, "deny")
        assert allowed is False
        assert "permanently denied" in msg


class TestCheckSecurityGateConfirm:
    def test_confirm_with_auto_approve(self):
        from ollama_arena.mcp.security import check_security_gate
        env = {k: v for k, v in os.environ.items() if k != "PYTEST_CURRENT_TEST"}
        env["ARENA_AUTO_APPROVE"] = "1"
        with mock.patch.dict(os.environ, env, clear=True):
            allowed, msg = check_security_gate("risky_tool", {}, "confirm")
        assert allowed is True

    def test_confirm_non_tty_denied(self):
        from ollama_arena.mcp.security import check_security_gate
        env = {k: v for k, v in os.environ.items() if k != "PYTEST_CURRENT_TEST"}
        env.pop("ARENA_AUTO_APPROVE", None)
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch("sys.stdin.isatty", return_value=False):
                allowed, msg = check_security_gate("risky_tool", {}, "confirm")
        assert allowed is False
        assert "non-interactive" in msg


# ──────────────────────────────────────────────────────────────────────────────
# visualize/charts.py — HTML generators (no plotly calls, test non-plotly paths)
# ──────────────────────────────────────────────────────────────────────────────

class TestLeaderboardTableHtml:
    def test_empty_returns_no_matches(self):
        from ollama_arena.visualize.charts import leaderboard_table_html
        html = leaderboard_table_html([])
        assert "No matches yet" in html

    def test_one_entry(self):
        from ollama_arena.visualize.charts import leaderboard_table_html
        entry = {
            "rank": 1, "model": "phi-4", "elo": 1250.0,
            "wins": 10, "losses": 2, "draws": 1, "matches": 13,
            "win_rate": 0.769, "trend": "up", "trend_delta": 15.0, "elo_ci": 50.0,
        }
        html = leaderboard_table_html([entry])
        assert "phi-4" in html
        assert "1250" in html
        assert "▲" in html

    def test_trend_stable(self):
        from ollama_arena.visualize.charts import leaderboard_table_html
        entry = {
            "rank": 1, "model": "qwen", "elo": 1200.0,
            "wins": 5, "losses": 5, "draws": 0, "matches": 10,
            "win_rate": 0.5, "trend": "stable", "trend_delta": 0.0,
        }
        html = leaderboard_table_html([entry])
        assert "—" in html

    def test_trend_down(self):
        from ollama_arena.visualize.charts import leaderboard_table_html
        entry = {
            "rank": 2, "model": "llama", "elo": 1150.0,
            "wins": 3, "losses": 8, "draws": 0, "matches": 11,
            "win_rate": 0.27, "trend": "down", "trend_delta": -20.0,
        }
        html = leaderboard_table_html([entry])
        assert "▼" in html


class TestAntiLeaderboardTableHtml:
    def test_empty_returns_no_data(self):
        from ollama_arena.visualize.charts import anti_leaderboard_table_html
        html = anti_leaderboard_table_html([])
        assert "No hallucination data" in html

    def test_one_entry_high_rate(self):
        from ollama_arena.visualize.charts import anti_leaderboard_table_html
        entry = {
            "rank": 1, "model": "bad-model", "halluc_rate": 0.35,
            "hallucinations": 7, "total_checked": 20,
        }
        html = anti_leaderboard_table_html([entry])
        assert "bad-model" in html
        assert "35.0%" in html

    def test_low_rate_entry(self):
        from ollama_arena.visualize.charts import anti_leaderboard_table_html
        entry = {
            "rank": 1, "model": "good-model", "halluc_rate": 0.02,
            "hallucinations": 1, "total_checked": 50,
        }
        html = anti_leaderboard_table_html([entry])
        assert "good-model" in html


class TestCategoryEloRadarFallback:
    def test_empty_profiles_returns_no_data(self):
        from ollama_arena.visualize.charts import _category_elo_radar_fallback
        html = _category_elo_radar_fallback({}, 1200.0)
        assert "No category data" in html

    def test_with_profiles_returns_table(self):
        from ollama_arena.visualize.charts import _category_elo_radar_fallback
        profiles = {
            "phi-4": [{"category": "coding", "elo": 1250.0}],
            "qwen": [{"category": "coding", "elo": 1180.0}, {"category": "math", "elo": 1200.0}],
        }
        html = _category_elo_radar_fallback(profiles, 1200.0)
        assert "phi-4" in html
        assert "coding" in html


class TestCategoryEloRadarHtml:
    def test_empty_profiles_returns_no_data(self):
        from ollama_arena.visualize.charts import category_elo_radar_html
        html = category_elo_radar_html({}, 1200.0)
        assert "No category data" in html

    def test_with_profiles(self):
        from ollama_arena.visualize.charts import category_elo_radar_html
        profiles = {
            "phi-4": [{"category": "coding", "elo": 1250.0}],
        }
        html = category_elo_radar_html(profiles, 1200.0)
        assert len(html) > 0


class TestPerformanceChartHtml:
    def test_empty_returns_no_data(self):
        from ollama_arena.visualize.charts import performance_chart_html
        html = performance_chart_html([])
        assert "No performance data" in html

    def test_dict_with_models(self):
        from ollama_arena.visualize.charts import performance_chart_html
        # Source uses deprecated plotly 'titlefont' — skip rendering path
        with mock.patch("ollama_arena.visualize.charts._require_plotly") as m:
            go = mock.MagicMock()
            fig = mock.MagicMock()
            go.Figure.return_value = fig
            go.Bar.return_value = mock.MagicMock()
            fig.to_html.return_value = "<div>chart</div>"
            m.return_value = go
            html = performance_chart_html([{"model": "phi-4", "tps_mean": 50.0, "latency_mean_s": 0.5}])
        assert len(html) > 0

    def test_dict_without_models(self):
        from ollama_arena.visualize.charts import performance_chart_html
        html = performance_chart_html({"no_models": True})
        assert "No performance data" in html


class TestFullDashboardHtml:
    def test_renders_title(self):
        from ollama_arena.visualize.charts import full_dashboard_html
        html = full_dashboard_html([], [], ["coding", "math"], title="Test Arena")
        assert "Test Arena" in html
        assert "Leaderboard" in html

    def test_renders_with_leaderboard_entry(self):
        from ollama_arena.visualize.charts import full_dashboard_html
        entry = {
            "rank": 1, "model": "phi-4", "elo": 1250.0,
            "wins": 10, "losses": 2, "draws": 1, "matches": 13,
            "win_rate": 0.769, "trend": "stable", "trend_delta": 0.0,
        }
        html = full_dashboard_html([entry], [], ["coding"])
        assert "phi-4" in html


class TestExportDashboard:
    def test_writes_file(self, tmp_path):
        from ollama_arena.visualize.charts import export_dashboard
        out = str(tmp_path / "dashboard.html")
        result = export_dashboard(out, [], [], ["coding"])
        assert result == out
        content = open(out).read()
        assert "<!DOCTYPE html>" in content
