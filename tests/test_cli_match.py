"""Tests for cli/match.py — match, benchmark, tournament, royale commands."""
from __future__ import annotations
import sys
import unittest.mock as mock
import pytest


def _mc():
    c = mock.MagicMock()
    # Rich Progress context manager
    mock_prog = mock.MagicMock()
    mock_prog.__enter__ = mock.MagicMock(return_value=mock_prog)
    mock_prog.__exit__ = mock.MagicMock(return_value=False)
    c.status.return_value = mock_prog
    return c


def _make_args(**kwargs):
    args = mock.MagicMock()
    args.db = ":memory:"
    args.ollama = "http://localhost:11434"
    args.backend = None
    args.api_key = None
    args.models = "model_a,model_b"
    args.category = "coding"
    args.n = 2
    args.difficulty = None
    args.verbose = False
    args.share = False
    args.tools = False
    args.dataset = None
    args.dataset_limit = None
    args.compare = False
    args.fail_below = None
    for k, v in kwargs.items():
        setattr(args, k, v)
    return args


def _make_match_result(a_wins=2, b_wins=1):
    r = mock.MagicMock()
    r.a_wins = a_wins
    r.b_wins = b_wins
    r.elo_a_before = 1200.0
    r.elo_a_after = 1215.0
    r.elo_b_before = 1200.0
    r.elo_b_after = 1185.0
    r.a_win_rate = a_wins / (a_wins + b_wins)
    r.b_win_rate = b_wins / (a_wins + b_wins)
    r.duration_s = 5.0
    r.match_id = 1
    return r


def _make_arena_mock(is_alive=True, match_result=None):
    arena = mock.MagicMock()
    arena.client.is_alive.return_value = is_alive
    arena.client.name = "ollama"
    arena.judge = None
    if match_result is None:
        match_result = _make_match_result()
    arena.run_match.return_value = match_result

    from ollama_arena.backends.base import GenResult
    gen = GenResult(text="def add(a, b): return a + b", model="m", tps=10.0, latency_s=0.5)
    arena.client.generate.return_value = gen
    arena.leaderboard.return_value = []
    arena.elo.match_history.return_value = []
    arena.elo.leaderboard.return_value = []
    arena.elo.category_stats.return_value = []
    return arena


class TestCmdMatch:
    def test_single_model_exits(self):
        from ollama_arena.cli.match import cmd_match
        args = _make_args(models="only_one")
        mock_c = _mc()
        with mock.patch("ollama_arena.cli.match._console", return_value=mock_c), \
             pytest.raises(SystemExit):
            cmd_match(args)

    def test_backend_not_alive_exits(self):
        from ollama_arena.cli.match import cmd_match
        args = _make_args()
        mock_c = _mc()
        arena = _make_arena_mock(is_alive=False)

        with mock.patch("ollama_arena.cli.match._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.match._make_arena", return_value=arena), \
             mock.patch("ollama_arena.cli.data.cmd_leaderboard"), \
             pytest.raises(SystemExit):
            cmd_match(args)

    def test_basic_match(self):
        from ollama_arena.cli.match import cmd_match
        args = _make_args()
        mock_c = _mc()
        arena = _make_arena_mock()

        mock_progress = mock.MagicMock()
        mock_progress.__enter__ = mock.MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("ollama_arena.cli.match._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.match._make_arena", return_value=arena), \
             mock.patch("ollama_arena.cli.data.cmd_leaderboard"), \
             mock.patch("ollama_arena.elo.EloStore"), \
             mock.patch("rich.progress.Progress", return_value=mock_progress), \
             mock.patch("rich.rule.Rule"), \
             mock.patch("rich.panel.Panel"):
            cmd_match(args)

        arena.run_match.assert_called()

    def test_match_with_dataset(self):
        from ollama_arena.cli.match import cmd_match
        args = _make_args(dataset="humaneval", dataset_limit=10)
        mock_c = _mc()
        arena = _make_arena_mock()
        arena.load_hf_dataset.return_value = 10

        mock_progress = mock.MagicMock()
        mock_progress.__enter__ = mock.MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("ollama_arena.cli.match._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.match._make_arena", return_value=arena), \
             mock.patch("ollama_arena.cli.data.cmd_leaderboard"), \
             mock.patch("ollama_arena.elo.EloStore"), \
             mock.patch("rich.progress.Progress", return_value=mock_progress), \
             mock.patch("rich.rule.Rule"), \
             mock.patch("rich.panel.Panel"):
            cmd_match(args)

        arena.load_hf_dataset.assert_called_once()

    def test_match_three_models_two_pairs(self):
        from ollama_arena.cli.match import cmd_match
        args = _make_args(models="a,b,c", n=1)
        mock_c = _mc()
        arena = _make_arena_mock()

        mock_progress = mock.MagicMock()
        mock_progress.__enter__ = mock.MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("ollama_arena.cli.match._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.match._make_arena", return_value=arena), \
             mock.patch("ollama_arena.cli.data.cmd_leaderboard"), \
             mock.patch("ollama_arena.elo.EloStore"), \
             mock.patch("rich.progress.Progress", return_value=mock_progress), \
             mock.patch("rich.rule.Rule"), \
             mock.patch("rich.panel.Panel"):
            cmd_match(args)

        # 3 models = 3 pairs (a vs b, a vs c, b vs c)
        assert arena.run_match.call_count == 3

    def test_match_b_wins(self):
        from ollama_arena.cli.match import cmd_match
        args = _make_args()
        mock_c = _mc()
        arena = _make_arena_mock(match_result=_make_match_result(a_wins=1, b_wins=3))

        mock_progress = mock.MagicMock()
        mock_progress.__enter__ = mock.MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("ollama_arena.cli.match._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.match._make_arena", return_value=arena), \
             mock.patch("ollama_arena.cli.data.cmd_leaderboard"), \
             mock.patch("ollama_arena.elo.EloStore"), \
             mock.patch("rich.progress.Progress", return_value=mock_progress), \
             mock.patch("rich.rule.Rule"), \
             mock.patch("rich.panel.Panel"):
            cmd_match(args)

    def test_match_draw(self):
        from ollama_arena.cli.match import cmd_match
        args = _make_args()
        mock_c = _mc()
        arena = _make_arena_mock(match_result=_make_match_result(a_wins=2, b_wins=2))

        mock_progress = mock.MagicMock()
        mock_progress.__enter__ = mock.MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("ollama_arena.cli.match._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.match._make_arena", return_value=arena), \
             mock.patch("ollama_arena.cli.data.cmd_leaderboard"), \
             mock.patch("ollama_arena.elo.EloStore"), \
             mock.patch("rich.progress.Progress", return_value=mock_progress), \
             mock.patch("rich.rule.Rule"), \
             mock.patch("rich.panel.Panel"):
            cmd_match(args)


class TestCmdMatchVerbose:
    def test_verbose_mode_calls_print_task_detail(self):
        from ollama_arena.cli.match import cmd_match
        args = _make_args(verbose=True)
        mock_c = _mc()
        arena = _make_arena_mock()

        def run_match_with_callback(*a, **kw):
            arena._on_task_done("task_1", 0.9, 0.1, "a_wins", "instr", "resp_a", "resp_b", "exp")
            return _make_match_result()

        arena.run_match.side_effect = run_match_with_callback

        mock_progress = mock.MagicMock()
        mock_progress.__enter__ = mock.MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("ollama_arena.cli.match._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.match._make_arena", return_value=arena), \
             mock.patch("ollama_arena.cli.data.cmd_leaderboard"), \
             mock.patch("ollama_arena.elo.EloStore"), \
             mock.patch("ollama_arena.cli.match._print_task_detail") as mock_ptd, \
             mock.patch("rich.progress.Progress", return_value=mock_progress), \
             mock.patch("rich.rule.Rule"), \
             mock.patch("rich.panel.Panel"):
            cmd_match(args)


class TestCmdBenchmark:
    def test_backend_not_alive_exits(self):
        from ollama_arena.cli.match import cmd_benchmark
        args = _make_args(models="model_a")
        mock_c = _mc()
        arena = _make_arena_mock(is_alive=False)

        with mock.patch("ollama_arena.cli.match._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.match._make_arena", return_value=arena), \
             pytest.raises(SystemExit):
            cmd_benchmark(args)

    def test_basic_benchmark(self):
        from ollama_arena.cli.match import cmd_benchmark
        args = _make_args(models="model_a", compare=False, fail_below=None)
        mock_c = _mc()
        arena = _make_arena_mock()

        from ollama_arena.backends.base import GenResult
        gen = GenResult(text="answer", model="m", tps=10.0, latency_s=0.5)
        arena.client.generate.return_value = gen

        mock_progress = mock.MagicMock()
        mock_progress.__enter__ = mock.MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("ollama_arena.cli.match._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.match._make_arena", return_value=arena), \
             mock.patch("ollama_arena.tasks.get_tasks", return_value=[
                 {"instruction": "task1", "expected": "ans"},
             ] * 10), \
             mock.patch("ollama_arena.evaluator.evaluate", return_value=0.8), \
             mock.patch("rich.progress.Progress", return_value=mock_progress), \
             mock.patch("rich.panel.Panel"):
            cmd_benchmark(args)

        arena.elo.save_benchmark.assert_called()

    def test_benchmark_empty_category_does_not_crash(self):
        """Regression test: if get_tasks() returns no tasks for a category (or
        every score in a category comes back None), the per-category average
        used to divide by zero and crash the whole benchmark with an uncaught
        ZeroDivisionError. It must now degrade to a 0.0 score for that category
        instead of crashing."""
        from ollama_arena.cli.match import cmd_benchmark
        args = _make_args(models="model_a", compare=False, fail_below=None)
        mock_c = _mc()
        arena = _make_arena_mock()

        from ollama_arena.backends.base import GenResult
        gen = GenResult(text="answer", model="m", tps=10.0, latency_s=0.5)
        arena.client.generate.return_value = gen

        mock_progress = mock.MagicMock()
        mock_progress.__enter__ = mock.MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("ollama_arena.cli.match._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.match._make_arena", return_value=arena), \
             mock.patch("ollama_arena.tasks.get_tasks", return_value=[]), \
             mock.patch("ollama_arena.evaluator.evaluate", return_value=0.8), \
             mock.patch("rich.progress.Progress", return_value=mock_progress), \
             mock.patch("rich.panel.Panel"):
            cmd_benchmark(args)  # must not raise ZeroDivisionError

        arena.elo.save_benchmark.assert_called()

    def test_benchmark_compare_two_models(self):
        from ollama_arena.cli.match import cmd_benchmark
        args = _make_args(models="model_a,model_b", compare=True, fail_below=None)
        mock_c = _mc()
        arena = _make_arena_mock()

        from ollama_arena.backends.base import GenResult
        gen = GenResult(text="answer", model="m", tps=10.0, latency_s=0.5)
        arena.client.generate.return_value = gen

        mock_progress = mock.MagicMock()
        mock_progress.__enter__ = mock.MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("ollama_arena.cli.match._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.match._make_arena", return_value=arena), \
             mock.patch("ollama_arena.tasks.get_tasks", return_value=[
                 {"instruction": "task1", "expected": "ans"},
             ] * 6), \
             mock.patch("ollama_arena.evaluator.evaluate", return_value=0.7), \
             mock.patch("rich.progress.Progress", return_value=mock_progress), \
             mock.patch("rich.panel.Panel"):
            cmd_benchmark(args)

        mock_c.print.assert_called()

    def test_benchmark_fail_below_threshold(self):
        from ollama_arena.cli.match import cmd_benchmark
        args = _make_args(models="model_a", fail_below=90.0)
        mock_c = _mc()
        arena = _make_arena_mock()

        from ollama_arena.backends.base import GenResult
        gen = GenResult(text="", model="m", tps=0.0, latency_s=0.5, error="fail")
        arena.client.generate.return_value = gen

        mock_progress = mock.MagicMock()
        mock_progress.__enter__ = mock.MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("ollama_arena.cli.match._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.match._make_arena", return_value=arena), \
             mock.patch("ollama_arena.tasks.get_tasks", return_value=[
                 {"instruction": "task1", "expected": "ans"},
             ] * 6), \
             mock.patch("ollama_arena.evaluator.evaluate", return_value=0.0), \
             mock.patch("rich.progress.Progress", return_value=mock_progress), \
             mock.patch("rich.panel.Panel"), \
             pytest.raises(SystemExit):
            cmd_benchmark(args)


class TestCmdTournament:
    def test_single_model_exits(self):
        from ollama_arena.cli.match import cmd_tournament
        args = _make_args(models="only_one")
        mock_c = _mc()

        with mock.patch("ollama_arena.cli.match._console", return_value=mock_c), \
             pytest.raises(SystemExit):
            cmd_tournament(args)

    def test_basic_tournament(self):
        from ollama_arena.cli.match import cmd_tournament
        args = _make_args(models="a,b,c", n=1)
        mock_c = _mc()
        arena = _make_arena_mock()

        with mock.patch("ollama_arena.cli.match._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.match._make_arena", return_value=arena), \
             mock.patch("ollama_arena.cli.data.cmd_leaderboard"), \
             mock.patch("ollama_arena.elo.EloStore"):
            cmd_tournament(args)

        arena.run_tournament.assert_called_once()

    def test_tournament_with_dataset(self):
        from ollama_arena.cli.match import cmd_tournament
        args = _make_args(models="a,b", n=2, dataset="humaneval", dataset_limit=5)
        mock_c = _mc()
        arena = _make_arena_mock()
        arena.load_hf_dataset.return_value = 5

        with mock.patch("ollama_arena.cli.match._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.match._make_arena", return_value=arena), \
             mock.patch("ollama_arena.cli.data.cmd_leaderboard"), \
             mock.patch("ollama_arena.elo.EloStore"):
            cmd_tournament(args)

        arena.load_hf_dataset.assert_called_once()


class TestCmdRoyale:
    def _make_royale_result(self):
        r = mock.MagicMock()
        r.rankings = [
            {"rank": 1, "model": "a", "total_score": 8.5, "elo_after": 1250.0},
            {"rank": 2, "model": "b", "total_score": 6.0, "elo_after": 1200.0},
            {"rank": 3, "model": "c", "total_score": 4.5, "elo_after": 1150.0},
        ]
        r.winner = "a"
        r.duration_s = 12.0
        r.royale_id = 1
        r.strategy = "sequential"
        return r

    def test_less_than_three_models_exits(self):
        from ollama_arena.cli.match import cmd_royale
        args = _make_args(models="a,b")
        mock_c = _mc()

        with mock.patch("ollama_arena.cli.match._console", return_value=mock_c), \
             pytest.raises(SystemExit):
            cmd_royale(args)

    def test_backend_not_alive_exits(self):
        from ollama_arena.cli.match import cmd_royale
        args = _make_args(models="a,b,c")
        mock_c = _mc()
        arena = _make_arena_mock(is_alive=False)

        with mock.patch("ollama_arena.cli.match._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.match._make_arena", return_value=arena), \
             pytest.raises(SystemExit):
            cmd_royale(args)

    def test_basic_royale(self):
        from ollama_arena.cli.match import cmd_royale
        args = _make_args(models="a,b,c", n=2)
        mock_c = _mc()
        arena = _make_arena_mock()
        royale_result = self._make_royale_result()
        arena.run_royale.return_value = royale_result
        arena.elo.royale_entries.return_value = []

        mock_progress = mock.MagicMock()
        mock_progress.__enter__ = mock.MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("ollama_arena.cli.match._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.match._make_arena", return_value=arena), \
             mock.patch("ollama_arena.cli.data.cmd_leaderboard"), \
             mock.patch("ollama_arena.elo.EloStore"), \
             mock.patch("rich.progress.Progress", return_value=mock_progress), \
             mock.patch("rich.rule.Rule"), \
             mock.patch("rich.panel.Panel"):
            cmd_royale(args)

        arena.run_royale.assert_called_once()

    def test_royale_with_entries_exports_report(self):
        from ollama_arena.cli.match import cmd_royale
        args = _make_args(models="a,b,c", n=2)
        mock_c = _mc()
        arena = _make_arena_mock()
        royale_result = self._make_royale_result()
        arena.run_royale.return_value = royale_result
        arena.elo.royale_entries.return_value = [{"model": "a", "score": 8.5}]

        mock_progress = mock.MagicMock()
        mock_progress.__enter__ = mock.MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("ollama_arena.cli.match._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.match._make_arena", return_value=arena), \
             mock.patch("ollama_arena.cli.data.cmd_leaderboard"), \
             mock.patch("ollama_arena.elo.EloStore"), \
             mock.patch("ollama_arena.visualize.export_royale_report", return_value="report.html"), \
             mock.patch("rich.progress.Progress", return_value=mock_progress), \
             mock.patch("rich.rule.Rule"), \
             mock.patch("rich.panel.Panel"):
            cmd_royale(args)
