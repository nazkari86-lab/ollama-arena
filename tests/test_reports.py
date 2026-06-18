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
