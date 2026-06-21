"""Tests for cli/data.py — data, reporting, and export commands."""
from __future__ import annotations
import os
import sys
import unittest.mock as mock
import pytest


def _mc():
    return mock.MagicMock()


def _make_args(**kwargs):
    args = mock.MagicMock()
    args.db = ":memory:"
    args.ollama = "http://localhost:11434"
    args.backend = None
    args.api_key = None
    args.model = None
    args.full = False
    args.export = False
    args.match = None
    args.last = 10
    args.pull = None
    args.refresh = None
    args.limit = None
    args.public = False
    args.out = "dashboard.html"
    args.task_id = "task_1"
    for k, v in kwargs.items():
        setattr(args, k, v)
    return args


def _make_leaderboard():
    return [
        {"rank": 1, "model": "llama3:8b", "elo": 1250.0, "wins": 10, "losses": 3,
         "draws": 1, "matches": 14, "win_rate": 0.714},
        {"rank": 2, "model": "phi3:mini", "elo": 1200.0, "wins": 5, "losses": 8,
         "draws": 1, "matches": 14, "win_rate": 0.357},
    ]


class TestCmdList:
    def test_no_models_found(self):
        from ollama_arena.cli.data import cmd_list
        args = _make_args()
        mock_c = _mc()
        mock_backend = mock.MagicMock()
        mock_backend.is_alive.return_value = True
        mock_backend.list_models.return_value = []
        mock_backend.name = "ollama"

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.backends.auto.auto_backend", return_value=mock_backend):
            cmd_list(args)

        mock_c.print.assert_called()

    def test_backend_not_alive_exits(self):
        from ollama_arena.cli.data import cmd_list
        args = _make_args()
        mock_c = _mc()
        mock_backend = mock.MagicMock()
        mock_backend.is_alive.return_value = False

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.backends.auto.auto_backend", return_value=mock_backend), \
             pytest.raises(SystemExit):
            cmd_list(args)

    def test_with_models(self):
        from ollama_arena.cli.data import cmd_list
        args = _make_args()
        mock_c = _mc()
        mock_backend = mock.MagicMock()
        mock_backend.is_alive.return_value = True
        mock_backend.list_models.return_value = ["llama3:8b", "phi3:mini"]
        mock_backend.name = "ollama"

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.backends.auto.auto_backend", return_value=mock_backend):
            cmd_list(args)

        mock_c.print.assert_called()


class TestCmdLeaderboard:
    def test_empty_leaderboard(self):
        from ollama_arena.cli.data import cmd_leaderboard
        args = _make_args()
        mock_c = _mc()
        mock_store = mock.MagicMock()
        mock_store.leaderboard.return_value = []

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.elo.EloStore", return_value=mock_store):
            cmd_leaderboard(args)

        mock_c.print.assert_called()

    def test_with_entries(self):
        from ollama_arena.cli.data import cmd_leaderboard
        args = _make_args()
        mock_c = _mc()
        mock_store = mock.MagicMock()
        mock_store.leaderboard.return_value = _make_leaderboard()

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.elo.EloStore", return_value=mock_store):
            cmd_leaderboard(args)

        mock_c.print.assert_called()


class TestCmdAntiLeaderboard:
    def test_empty(self):
        from ollama_arena.cli.data import cmd_anti_leaderboard
        args = _make_args()
        mock_c = _mc()
        mock_store = mock.MagicMock()
        mock_store.anti_leaderboard.return_value = []

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.elo.EloStore", return_value=mock_store):
            cmd_anti_leaderboard(args)

        mock_c.print.assert_called()

    def test_with_data(self):
        from ollama_arena.cli.data import cmd_anti_leaderboard
        args = _make_args()
        mock_c = _mc()
        mock_store = mock.MagicMock()
        mock_store.anti_leaderboard.return_value = [
            {"rank": 1, "model": "llama3:8b", "halluc_rate": 0.15,
             "hallucinations": 3, "total_checked": 20},
        ]

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.elo.EloStore", return_value=mock_store):
            cmd_anti_leaderboard(args)

        mock_c.print.assert_called()


class TestCmdImport:
    def test_file_not_found_exits(self, tmp_path):
        from ollama_arena.cli.data import cmd_import
        args = _make_args(file=str(tmp_path / "nonexistent.csv"))
        mock_c = _mc()

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             pytest.raises(SystemExit):
            cmd_import(args)

    def test_file_exists(self, tmp_path):
        from ollama_arena.cli.data import cmd_import
        data_file = tmp_path / "data.csv"
        data_file.write_text("col1,col2\nval1,val2\n")
        args = _make_args(file=str(data_file))
        mock_c = _mc()

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c):
            cmd_import(args)

        mock_c.print.assert_called()

    def test_csv_reports_actual_record_count(self, tmp_path):
        """Regression test: cmd_import used to always claim '150 tasks' were
        imported regardless of the file's real contents. It must now report
        the true number of data rows (header excluded)."""
        from ollama_arena.cli.data import cmd_import
        data_file = tmp_path / "mydata.csv"
        data_file.write_text("col1,col2\nval1,val2\nval3,val4\nval5,val6\n")
        args = _make_args(file=str(data_file))
        mock_c = _mc()

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c):
            cmd_import(args)

        printed = " ".join(str(c) for c in mock_c.print.call_args_list)
        assert "3" in printed
        assert "150" not in printed

    def test_json_reports_actual_record_count(self, tmp_path):
        from ollama_arena.cli.data import cmd_import
        data_file = tmp_path / "mydata.json"
        data_file.write_text('[{"a": 1}, {"a": 2}]')
        args = _make_args(file=str(data_file))
        mock_c = _mc()

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c):
            cmd_import(args)

        printed = " ".join(str(c) for c in mock_c.print.call_args_list)
        assert "2" in printed
        assert "150" not in printed

    def test_empty_csv_exits_nonzero(self, tmp_path):
        """A CSV with no data rows (just a header, or fully empty) must not
        claim a successful import — it has nothing to import."""
        from ollama_arena.cli.data import cmd_import
        data_file = tmp_path / "empty.csv"
        data_file.write_text("")
        args = _make_args(file=str(data_file))
        mock_c = _mc()

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             pytest.raises(SystemExit) as exc_info:
            cmd_import(args)

        assert exc_info.value.code == 1

    def test_malformed_json_exits_cleanly(self, tmp_path):
        """Invalid JSON must produce a clean parse error and exit 1, not an
        uncaught JSONDecodeError traceback."""
        from ollama_arena.cli.data import cmd_import
        data_file = tmp_path / "bad.json"
        data_file.write_text("not valid json{{{")
        args = _make_args(file=str(data_file))
        mock_c = _mc()

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             pytest.raises(SystemExit) as exc_info:
            cmd_import(args)

        assert exc_info.value.code == 1
        printed = " ".join(str(c) for c in mock_c.print.call_args_list)
        assert "Failed to parse" in printed

    def test_unsupported_extension_exits_cleanly(self, tmp_path):
        from ollama_arena.cli.data import cmd_import
        data_file = tmp_path / "data.xlsx"
        data_file.write_text("irrelevant")
        args = _make_args(file=str(data_file))
        mock_c = _mc()

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             pytest.raises(SystemExit) as exc_info:
            cmd_import(args)

        assert exc_info.value.code == 1


class TestCmdTasks:
    def test_basic(self):
        from ollama_arena.cli.data import cmd_tasks
        args = _make_args()
        mock_c = _mc()

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.tasks.task_stats", return_value={"coding": 10, "math": 5}), \
             mock.patch("ollama_arena.tasks.get_tasks", return_value=[
                 {"difficulty": "easy"}, {"difficulty": "medium"}, {"difficulty": "hard"}
             ]), \
             mock.patch("ollama_arena.tasks.list_languages", return_value=["python", "javascript"]):
            cmd_tasks(args)

        mock_c.print.assert_called()


class TestCmdDatasets:
    def test_list_datasets(self):
        from ollama_arena.cli.data import cmd_datasets
        args = _make_args(pull=None, refresh=None)
        mock_c = _mc()
        mock_ds = [
            {"name": "humaneval", "hf_id": "openai/humaneval",
             "category": "coding", "cached": True, "license": "MIT"},
        ]

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.datasets.available_datasets", return_value=mock_ds), \
             mock.patch("ollama_arena.datasets.load_dataset", return_value=[]), \
             mock.patch("ollama_arena.datasets.refresh_dataset", return_value=0):
            cmd_datasets(args)

        mock_c.print.assert_called()

    def test_pull_datasets(self):
        from ollama_arena.cli.data import cmd_datasets
        args = _make_args(pull="humaneval,mbpp")
        mock_c = _mc()

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.datasets.available_datasets", return_value=[]), \
             mock.patch("ollama_arena.datasets.load_dataset", return_value=[{"x": 1}, {"x": 2}]) as mock_load, \
             mock.patch("ollama_arena.datasets.refresh_dataset", return_value=0):
            cmd_datasets(args)

        assert mock_load.call_count == 2

    def test_refresh_datasets(self):
        from ollama_arena.cli.data import cmd_datasets
        args = _make_args(refresh="humaneval")
        mock_c = _mc()

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.datasets.available_datasets", return_value=[]), \
             mock.patch("ollama_arena.datasets.load_dataset", return_value=[]), \
             mock.patch("ollama_arena.datasets.refresh_dataset", return_value=5) as mock_refresh:
            cmd_datasets(args)

        mock_refresh.assert_called_once()


class TestCmdResults:
    def _make_match(self, id=1):
        import time
        return {
            "id": id, "model_a": "llama3:8b", "model_b": "phi3:mini",
            "category": "coding", "tasks": 10, "a_wins": 7, "b_wins": 2,
            "draws": 1, "winner": "llama3:8b", "ts": time.time(),
        }

    def test_no_matches(self):
        from ollama_arena.cli.data import cmd_results
        args = _make_args()
        mock_c = _mc()
        mock_store = mock.MagicMock()
        mock_store.recent_matches_summary.return_value = []

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.elo.EloStore", return_value=mock_store):
            cmd_results(args)

        mock_c.print.assert_called()

    def test_recent_matches_list(self):
        from ollama_arena.cli.data import cmd_results
        args = _make_args(match=None, last=10)
        mock_c = _mc()
        mock_store = mock.MagicMock()
        mock_store.recent_matches_summary.return_value = [self._make_match(1), self._make_match(2)]

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.elo.EloStore", return_value=mock_store):
            cmd_results(args)

        mock_c.print.assert_called()

    def test_show_specific_match(self):
        from ollama_arena.cli.data import cmd_results
        args = _make_args(match=1, full=False, export=False)
        mock_c = _mc()
        mock_store = mock.MagicMock()
        mock_store.tasks_for_match.return_value = []

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.elo.EloStore", return_value=mock_store), \
             mock.patch("ollama_arena.cli.data._show_match_detail"):
            cmd_results(args)

    def test_show_specific_match_with_export(self):
        from ollama_arena.cli.data import cmd_results
        args = _make_args(match=1, full=False, export=True)
        mock_c = _mc()
        mock_store = mock.MagicMock()
        mock_store.tasks_for_match.return_value = [
            {"task_id": "t1", "score_a": 0.9, "score_b": 0.1, "outcome": "a_wins"}
        ]
        mock_store.match_history.return_value = [self._make_match(1)]

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.elo.EloStore", return_value=mock_store), \
             mock.patch("ollama_arena.cli.data._show_match_detail"), \
             mock.patch("ollama_arena.visualize.export_match_report", return_value="report.html"):
            cmd_results(args)

    def test_export_requested_but_match_not_in_history_warns(self):
        """Regression test: previously, if --export was passed but the match id
        wasn't present in match_history() (e.g. older than the 200-match window),
        the command silently did nothing — no file, no warning, no error. The
        user has no way to know the export didn't happen. It must now print an
        explicit warning instead of failing silently."""
        from ollama_arena.cli.data import cmd_results
        args = _make_args(match=999, full=False, export=True)
        mock_c = _mc()
        mock_store = mock.MagicMock()
        mock_store.tasks_for_match.return_value = [
            {"task_id": "t1", "score_a": 0.9, "score_b": 0.1, "outcome": "a_wins"}
        ]
        mock_store.match_history.return_value = [self._make_match(1)]  # id=1, not 999

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.elo.EloStore", return_value=mock_store), \
             mock.patch("ollama_arena.cli.data._show_match_detail"), \
             mock.patch("ollama_arena.visualize.export_match_report") as mock_export:
            cmd_results(args)

        mock_export.assert_not_called()
        printed = " ".join(str(c) for c in mock_c.print.call_args_list)
        assert "Could not export" in printed or "999" in printed


class TestCmdInspect:
    def _make_task_history(self):
        import time
        return [
            {
                "model_a": "llama3:8b", "model_b": "phi3:mini",
                "instruction": "Write a function to add two numbers",
                "expected": "def add(a, b): return a + b",
                "response_a": "def add(a, b): return a + b",
                "response_b": "return a + b",
                "score_a": 0.9, "score_b": 0.3, "outcome": "a_wins",
                "ts": time.time(),
            }
        ]

    def test_no_history(self):
        from ollama_arena.cli.data import cmd_inspect
        args = _make_args(task_id="nonexistent", full=False)
        mock_c = _mc()
        mock_store = mock.MagicMock()
        mock_store.task_history.return_value = []

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.elo.EloStore", return_value=mock_store):
            cmd_inspect(args)

        mock_c.print.assert_called()

    def test_with_history(self):
        from ollama_arena.cli.data import cmd_inspect
        args = _make_args(task_id="task_1", full=False)
        mock_c = _mc()
        mock_store = mock.MagicMock()
        mock_store.task_history.return_value = self._make_task_history()

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.elo.EloStore", return_value=mock_store):
            cmd_inspect(args)

        mock_c.print.assert_called()

    def test_with_full_mode(self):
        from ollama_arena.cli.data import cmd_inspect
        args = _make_args(task_id="task_1", full=True)
        mock_c = _mc()
        mock_store = mock.MagicMock()
        mock_store.task_history.return_value = self._make_task_history()

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.elo.EloStore", return_value=mock_store):
            cmd_inspect(args)

        mock_c.print.assert_called()

    def test_history_with_no_expected(self):
        from ollama_arena.cli.data import cmd_inspect
        import time
        args = _make_args(task_id="task_2", full=False)
        mock_c = _mc()
        mock_store = mock.MagicMock()
        mock_store.task_history.return_value = [
            {
                "model_a": "a", "model_b": "b",
                "instruction": "question", "expected": "",
                "response_a": "ans a", "response_b": "ans b",
                "score_a": 0.5, "score_b": 0.5, "outcome": "draw",
                "ts": time.time(),
            }
        ]

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.elo.EloStore", return_value=mock_store):
            cmd_inspect(args)


class TestCmdReport:
    def test_no_data(self):
        from ollama_arena.cli.data import cmd_report
        args = _make_args(model=None)
        mock_c = _mc()
        mock_store = mock.MagicMock()
        mock_store.leaderboard.return_value = []

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.elo.EloStore", return_value=mock_store):
            cmd_report(args)

        mock_c.print.assert_called()

    def test_with_data_no_filter(self):
        from ollama_arena.cli.data import cmd_report
        args = _make_args(model=None)
        mock_c = _mc()
        mock_store = mock.MagicMock()
        mock_store.leaderboard.return_value = _make_leaderboard()
        mock_store.category_stats.return_value = [
            {"category": "coding", "total": 10, "wins": 7, "losses": 2,
             "draws": 1, "win_rate": 0.7},
            {"category": "math", "total": 5, "wins": 1, "losses": 4,
             "draws": 0, "win_rate": 0.2},
        ]

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.elo.EloStore", return_value=mock_store):
            cmd_report(args)

        mock_c.print.assert_called()

    def test_with_model_filter(self):
        from ollama_arena.cli.data import cmd_report
        args = _make_args(model="llama3")
        mock_c = _mc()
        mock_store = mock.MagicMock()
        mock_store.leaderboard.return_value = _make_leaderboard()
        mock_store.category_stats.return_value = [
            {"category": "coding", "total": 8, "wins": 5, "losses": 2,
             "draws": 1, "win_rate": 0.625},
        ]

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.elo.EloStore", return_value=mock_store):
            cmd_report(args)

    def test_model_filter_no_match(self):
        from ollama_arena.cli.data import cmd_report
        args = _make_args(model="nonexistent_model_xyz")
        mock_c = _mc()
        mock_store = mock.MagicMock()
        mock_store.leaderboard.return_value = _make_leaderboard()

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.elo.EloStore", return_value=mock_store):
            cmd_report(args)

        mock_c.print.assert_called()

    def test_model_with_no_category_stats(self):
        from ollama_arena.cli.data import cmd_report
        args = _make_args(model=None)
        mock_c = _mc()
        mock_store = mock.MagicMock()
        mock_store.leaderboard.return_value = _make_leaderboard()
        mock_store.category_stats.return_value = []  # No stats for model

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.elo.EloStore", return_value=mock_store):
            cmd_report(args)


class TestCmdExport:
    def test_exports_dashboard(self, tmp_path):
        from ollama_arena.cli.data import cmd_export
        args = _make_args(out=str(tmp_path / "dashboard.html"))
        mock_c = _mc()
        mock_store = mock.MagicMock()
        mock_store.leaderboard.return_value = []
        mock_store.match_history.return_value = []
        mock_store.anti_leaderboard.return_value = []

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.elo.EloStore", return_value=mock_store), \
             mock.patch("ollama_arena.performance.PerfTracker") as mock_pt, \
             mock.patch("ollama_arena.visualize.export_dashboard", return_value=str(tmp_path / "dashboard.html")) as mock_ed, \
             mock.patch("ollama_arena.tasks.list_categories", return_value=["coding"]):
            mock_pt.return_value.stats.return_value = []
            cmd_export(args)

        mock_ed.assert_called_once()
        mock_c.print.assert_called()


class TestCmdPerf:
    def test_no_data(self):
        from ollama_arena.cli.data import cmd_perf
        args = _make_args()
        mock_c = _mc()

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.performance.PerfTracker") as mock_pt:
            mock_pt.return_value.stats.return_value = []
            cmd_perf(args)

        mock_c.print.assert_called()

    def test_with_stats(self):
        from ollama_arena.cli.data import cmd_perf
        args = _make_args()
        mock_c = _mc()
        perf_data = [
            {
                "model": "llama3:8b", "n_samples": 10,
                "tps_mean": 45.2, "tps_p95": 60.1,
                "latency_mean_s": 1.5, "latency_p95_s": 3.2, "ttft_mean_s": 0.3,
            }
        ]

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch("ollama_arena.performance.PerfTracker") as mock_pt:
            mock_pt.return_value.stats.return_value = perf_data
            cmd_perf(args)

        mock_c.print.assert_called()


class TestCmdPublish:
    def test_no_token_exits(self):
        from ollama_arena.cli.data import cmd_publish
        args = _make_args()
        mock_c = _mc()
        env = {k: v for k, v in os.environ.items() if k not in ("GITHUB_TOKEN", "GH_TOKEN")}

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch.dict(os.environ, env, clear=True), \
             pytest.raises(SystemExit):
            cmd_publish(args)

    def test_publish_success(self):
        from ollama_arena.cli.data import cmd_publish
        args = _make_args()
        mock_c = _mc()
        mock_store = mock.MagicMock()
        mock_store.leaderboard.return_value = _make_leaderboard()
        mock_store.recent_matches_summary.return_value = []
        mock_store.benchmark_history.return_value = []
        mock_response = mock.MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"html_url": "https://gist.github.com/abc123"}

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch.dict(os.environ, {"GITHUB_TOKEN": "fake_token"}), \
             mock.patch("ollama_arena.elo.EloStore", return_value=mock_store), \
             mock.patch("ollama_arena.performance.PerfTracker") as mock_pt, \
             mock.patch("requests.post", return_value=mock_response):
            mock_pt.return_value.stats.return_value = []
            cmd_publish(args)

        mock_c.print.assert_called()

    def test_publish_failure(self):
        from ollama_arena.cli.data import cmd_publish
        args = _make_args()
        mock_c = _mc()
        mock_store = mock.MagicMock()
        mock_store.leaderboard.return_value = []
        mock_store.recent_matches_summary.return_value = []
        mock_store.benchmark_history.return_value = []
        mock_response = mock.MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch.dict(os.environ, {"GITHUB_TOKEN": "fake_token"}), \
             mock.patch("ollama_arena.elo.EloStore", return_value=mock_store), \
             mock.patch("ollama_arena.performance.PerfTracker") as mock_pt, \
             mock.patch("requests.post", return_value=mock_response), \
             pytest.raises(SystemExit):
            mock_pt.return_value.stats.return_value = []
            cmd_publish(args)

    def test_publish_exception(self):
        from ollama_arena.cli.data import cmd_publish
        args = _make_args()
        mock_c = _mc()
        mock_store = mock.MagicMock()
        mock_store.leaderboard.return_value = []
        mock_store.recent_matches_summary.return_value = []
        mock_store.benchmark_history.return_value = []

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch.dict(os.environ, {"GH_TOKEN": "fake_token"}), \
             mock.patch("ollama_arena.elo.EloStore", return_value=mock_store), \
             mock.patch("ollama_arena.performance.PerfTracker") as mock_pt, \
             mock.patch("requests.post", side_effect=Exception("network error")), \
             pytest.raises(SystemExit):
            mock_pt.return_value.stats.return_value = []
            cmd_publish(args)

    def test_publish_with_leaderboard_and_perf(self):
        from ollama_arena.cli.data import cmd_publish
        args = _make_args()
        mock_c = _mc()
        mock_store = mock.MagicMock()
        mock_store.leaderboard.return_value = _make_leaderboard()
        import time
        mock_store.recent_matches_summary.return_value = [
            {"id": 1, "model_a": "a", "model_b": "b", "category": "coding",
             "tasks": 5, "a_wins": 3, "b_wins": 2, "draws": 0,
             "winner": "a", "ts": time.time()}
        ]
        mock_store.benchmark_history.return_value = [
            {"model": "llama3:8b", "score": 85.5, "n_tasks": 30, "ts": time.time()}
        ]
        mock_response = mock.MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"html_url": "https://gist.github.com/xyz"}

        with mock.patch("ollama_arena.cli.data._console", return_value=mock_c), \
             mock.patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"}), \
             mock.patch("ollama_arena.elo.EloStore", return_value=mock_store), \
             mock.patch("ollama_arena.performance.PerfTracker") as mock_pt, \
             mock.patch("requests.post", return_value=mock_response):
            mock_pt.return_value.stats.return_value = [
                {"model": "llama3:8b", "n_samples": 5, "tps_mean": 40.0,
                 "tps_p95": 55.0, "latency_mean_s": 1.2, "latency_p95_s": 2.5, "ttft_mean_s": 0.2}
            ]
            cmd_publish(args)
