"""Tests for visualize/reports.py and category_elo_radar_html."""
import json
import time
from pathlib import Path

import pytest


SAMPLE_MATCH_INFO = {
    "model_a": "llama3", "model_b": "phi3",
    "category": "code", "ts": 1700000000.0,
    "score_a": 4.0, "score_b": 3.0,
    "elo_a_after": 1215.0, "elo_b_after": 1185.0,
}

SAMPLE_TASKS = [
    {
        "task_id": "task-001", "outcome": "a_wins",
        "instruction": "Write a hello world in Python",
        "response_a": "print('Hello world')",
        "response_b": "console.log('Hello')",
        "score_a": 1.0, "score_b": 0.0, "expected": "print('Hello world')",
    },
    {
        "task_id": "task-002", "outcome": "draw",
        "instruction": "Sort a list", "response_a": "sorted(lst)",
        "response_b": "lst.sort()", "score_a": 0.5, "score_b": 0.5, "expected": "",
    },
]


class TestExportMatchReport:
    def test_creates_json_and_html(self, tmp_path):
        from ollama_arena.visualize.reports import export_match_report
        result = export_match_report(
            match_id=42,
            info=SAMPLE_MATCH_INFO,
            tasks=SAMPLE_TASKS,
            out_dir=str(tmp_path),
        )
        assert Path(result).exists()
        assert Path(result).suffix == ".html"
        json_path = tmp_path / "match_42.json"
        assert json_path.exists()

    def test_json_content(self, tmp_path):
        from ollama_arena.visualize.reports import export_match_report
        export_match_report(42, SAMPLE_MATCH_INFO, SAMPLE_TASKS, str(tmp_path))
        data = json.loads((tmp_path / "match_42.json").read_text())
        assert data["match_id"] == 42
        assert data["type"] == "duel"
        assert data["model_a"] == "llama3"
        assert len(data["tasks"]) == 2

    def test_html_content(self, tmp_path):
        from ollama_arena.visualize.reports import export_match_report
        html_path = export_match_report(42, SAMPLE_MATCH_INFO, SAMPLE_TASKS, str(tmp_path))
        html = Path(html_path).read_text()
        assert "Match #42 Report" in html
        assert "llama3" in html
        assert "phi3" in html
        assert "a_wins" in html.lower() or "A WINS" in html

    def test_no_expected_field(self, tmp_path):
        from ollama_arena.visualize.reports import export_match_report
        tasks_no_expected = [
            {**SAMPLE_TASKS[0], "expected": ""},
        ]
        html_path = export_match_report(1, SAMPLE_MATCH_INFO, tasks_no_expected, str(tmp_path))
        html = Path(html_path).read_text()
        assert "Match #1 Report" in html

    def test_creates_output_dir(self, tmp_path):
        from ollama_arena.visualize.reports import export_match_report
        out = str(tmp_path / "nested" / "reports")
        export_match_report(99, SAMPLE_MATCH_INFO, [], out)
        assert Path(out).exists()


class TestExportRoyaleReport:
    def test_creates_files(self, tmp_path):
        from ollama_arena.visualize.reports import export_royale_report
        tasks = [
            {"task_id": "t1", "model": "a", "rank": 1, "score": 5.0,
             "response": "best answer", "tps": 30.0, "latency_s": 1.0, "ts": 0.0},
            {"task_id": "t1", "model": "b", "rank": 2, "score": 3.0,
             "response": "ok answer", "tps": 25.0, "latency_s": 1.2, "ts": 0.0},
        ]
        html_path = export_royale_report(
            royale_id=7,
            category="math",
            models=["a", "b"],
            tasks=tasks,
            out_dir=str(tmp_path),
        )
        assert Path(html_path).exists()
        assert (tmp_path / "royale_7.json").exists()

    def test_json_structure(self, tmp_path):
        from ollama_arena.visualize.reports import export_royale_report
        export_royale_report(7, "math", ["a", "b"], [], str(tmp_path))
        data = json.loads((tmp_path / "royale_7.json").read_text())
        assert data["royale_id"] == 7
        assert data["type"] == "royale"
        assert "a" in data["models"]

    def test_html_contains_models(self, tmp_path):
        from ollama_arena.visualize.reports import export_royale_report
        tasks = [
            {"task_id": "t1", "model": "llama3", "rank": 1, "score": 4.0,
             "response": "great", "tps": 40.0, "latency_s": 0.8, "ts": 0.0},
        ]
        html_path = export_royale_report(8, "code", ["llama3"], tasks, str(tmp_path))
        html = Path(html_path).read_text()
        assert "llama3" in html
        assert "Battle Royale #8" in html


class TestCategoryEloRadar:
    def test_fallback_no_profiles(self):
        from ollama_arena.visualize.charts import _category_elo_radar_fallback
        html = _category_elo_radar_fallback({}, 1200.0)
        assert "No category data" in html

    def test_fallback_with_data(self):
        from ollama_arena.visualize.charts import _category_elo_radar_fallback
        profiles = {
            "llama3": [
                {"category": "code", "elo": 1250.0, "matches": 5},
                {"category": "math", "elo": 1180.0, "matches": 3},
            ],
            "phi3": [
                {"category": "code", "elo": 1150.0, "matches": 4},
                {"category": "math", "elo": 1220.0, "matches": 3},
            ],
        }
        html = _fallback = _category_elo_radar_fallback(profiles, 1200.0)
        assert "llama3" in html
        assert "phi3" in html
        assert "code" in html
        assert "math" in html
        assert "1250" in html

    def test_category_elo_radar_html_no_plotly(self):
        """category_elo_radar_html falls back gracefully when plotly missing."""
        from ollama_arena.visualize.charts import category_elo_radar_html
        profiles = {
            "m1": [{"category": "reasoning", "elo": 1300.0, "matches": 10}],
        }
        html = category_elo_radar_html(profiles)
        # Should return something (either plotly chart or fallback table)
        assert len(html) > 0
        assert "m1" in html or "No category" in html

    def test_category_elo_radar_empty(self):
        from ollama_arena.visualize.charts import category_elo_radar_html
        html = category_elo_radar_html({})
        assert "No category data" in html


class TestHtmlInjectionFixes:
    """Model names / categories / task text must never be embedded raw into
    generated HTML — they can contain arbitrary LLM output or attacker-chosen
    model names."""

    def test_match_report_escapes_model_and_task_fields(self, tmp_path):
        from ollama_arena.visualize.reports import export_match_report
        info = {
            "model_a": "<img src=x onerror=alert(1)>", "model_b": "phi3",
            "category": "<b>cat</b>", "ts": 1700000000.0,
            "score_a": 1.0, "score_b": 0.0,
            "elo_a_after": 1200.0, "elo_b_after": 1190.0,
        }
        tasks = [{
            "task_id": "<svg onload=alert(2)>", "outcome": "a_wins",
            "instruction": "<script>steal()</script>",
            "response_a": "<b>bold</b>", "response_b": "plain",
            "score_a": 1.0, "score_b": 0.0, "expected": "<i>e</i>",
        }]
        html_path = export_match_report(1, info, tasks, str(tmp_path))
        html = Path(html_path).read_text()
        assert "<img src=x onerror=" not in html
        assert "<script>steal()</script>" not in html
        assert "<svg onload=" not in html
        assert "&lt;img src=x onerror=alert(1)&gt;" in html

    def test_royale_report_escapes_model_and_response_fields(self, tmp_path):
        from ollama_arena.visualize.reports import export_royale_report
        tasks = [{
            "task_id": "t1", "model": "<script>m</script>", "rank": 1,
            "score": 5.0, "response": "<script>alert(3)</script>",
            "tps": 30.0, "latency_s": 1.0, "ts": 0.0,
        }]
        html_path = export_royale_report(
            7, "<b>math</b>", ["<script>m</script>"], tasks, str(tmp_path),
        )
        html = Path(html_path).read_text()
        assert "<script>m</script>" not in html
        assert "<script>alert(3)</script>" not in html
        assert "&lt;script&gt;m&lt;/script&gt;" in html

    def test_leaderboard_table_escapes_model_name(self):
        from ollama_arena.visualize.charts import leaderboard_table_html
        board = [{
            "rank": 1, "model": "<script>alert(1)</script>", "elo": 1200.0,
            "wins": 1, "losses": 0, "draws": 0, "matches": 1, "win_rate": 1.0,
        }]
        html = leaderboard_table_html(board)
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html

    def test_anti_leaderboard_table_escapes_model_name(self):
        from ollama_arena.visualize.charts import anti_leaderboard_table_html
        board = [{
            "rank": 1, "model": "<script>alert(1)</script>",
            "halluc_rate": 0.5, "hallucinations": 1, "total_checked": 2,
        }]
        html = anti_leaderboard_table_html(board)
        assert "<script>alert(1)</script>" not in html

    def test_dashboard_title_is_escaped(self):
        from ollama_arena.visualize.charts import full_dashboard_html
        html = full_dashboard_html(
            [], [], ["code"], title="</title><script>alert(1)</script>",
        )
        assert "<script>alert(1)</script>" not in html

    def test_category_radar_fallback_escapes_model_and_category(self):
        from ollama_arena.visualize.charts import _category_elo_radar_fallback
        profiles = {
            "<script>m</script>": [{"category": "<script>c</script>", "elo": 1200.0}],
        }
        html = _category_elo_radar_fallback(profiles, 1200.0)
        assert "<script>m</script>" not in html
        assert "<script>c</script>" not in html


class TestLeaderboardEloCiFalsyZeroFix:
    def test_elo_ci_exactly_zero_is_rendered_not_dropped(self):
        from ollama_arena.visualize.charts import leaderboard_table_html
        board = [{
            "rank": 1, "model": "veteran-model", "elo": 1200.0,
            "wins": 100, "losses": 0, "draws": 0, "matches": 100,
            "win_rate": 1.0, "elo_ci": 0.0,
        }]
        html = leaderboard_table_html(board)
        assert "±0" in html

    def test_elo_ci_missing_renders_nothing(self):
        from ollama_arena.visualize.charts import leaderboard_table_html
        board = [{
            "rank": 1, "model": "m", "elo": 1200.0,
            "wins": 1, "losses": 0, "draws": 0, "matches": 1, "win_rate": 1.0,
        }]
        html = leaderboard_table_html(board)
        assert "confidence interval" not in html


class TestRadarHtmlEmptyCategories:
    def test_empty_categories_does_not_crash(self):
        from ollama_arena.visualize.charts import radar_html
        pytest.importorskip("plotly")
        matches = [{
            "model_a": "a", "model_b": "b", "score_a": 1.0, "score_b": 0.0,
            "category": "code",
        }]
        html = radar_html(matches, [])
        assert "No category data" in html


class TestPerformanceChartHtmlRendersWithoutCrash:
    def test_renders_real_plotly_figure(self):
        """performance_chart_html used to crash with ValueError on any
        non-empty input ('Invalid property... titlefont') under modern
        plotly versions. Verify the real (non-mocked) render path works."""
        plotly = pytest.importorskip("plotly")
        from ollama_arena.visualize.charts import performance_chart_html
        html = performance_chart_html([
            {"model": "phi-4", "tps_mean": 50.0, "latency_mean_s": 0.5},
        ])
        assert "phi-4" in html
        assert len(html) > 100


class TestEloTimelineMissingTimestamp:
    def test_missing_ts_key_does_not_crash(self):
        pytest.importorskip("plotly")
        from ollama_arena.visualize.charts import elo_timeline_html
        matches = [{
            "model_a": "a", "model_b": "b",
            "elo_a_after": 1200.0, "elo_b_after": 1190.0,
        }]
        html = elo_timeline_html(matches)
        assert len(html) > 0
