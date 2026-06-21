"""Tests for cli/__init__.py — main() argparse wiring."""
from __future__ import annotations
import sys
import unittest.mock as mock
import pytest


class TestMain:
    def test_no_args_exits_0(self):
        """Running with no subcommand prints help and exits 0."""
        from ollama_arena.cli import main
        with mock.patch("sys.argv", ["ollama-arena"]), \
             mock.patch("ollama_arena.cli.__version__", "0.0.0", create=True), \
             mock.patch("ollama_arena._banner.print_banner"), \
             mock.patch("ollama_arena.__version__", "0.0.0", create=True), \
             pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_match_subcommand_calls_cmd_match(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", [
            "ollama-arena", "match", "--models", "a,b",
            "--category", "coding", "-n", "2",
        ]), mock.patch("ollama_arena.cli.cmd_match") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_benchmark_subcommand_calls_cmd_benchmark(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", [
            "ollama-arena", "benchmark", "llama3:8b,phi3:mini",
        ]), mock.patch("ollama_arena.cli.cmd_benchmark") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_tournament_subcommand(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", [
            "ollama-arena", "tournament", "--models", "a,b,c",
        ]), mock.patch("ollama_arena.cli.cmd_tournament") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_royale_subcommand(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", [
            "ollama-arena", "royale", "--models", "a,b,c",
        ]), mock.patch("ollama_arena.cli.cmd_royale") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_council_subcommand(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", [
            "ollama-arena", "council", "--models", "a,b", "--topic", "AI ethics",
        ]), mock.patch("ollama_arena.cli.cmd_council") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_resolve_issue_subcommand(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", [
            "ollama-arena", "resolve-issue",
            "--model", "llama3:8b",
            "--issue", "Fix the bug",
        ]), mock.patch("ollama_arena.cli.cmd_resolve_issue") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_optimize_prompt_subcommand(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", [
            "ollama-arena", "optimize-prompt", "--model", "llama3:8b",
        ]), mock.patch("ollama_arena.cli.cmd_optimize_prompt") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_review_pr_subcommand(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", [
            "ollama-arena", "review-pr", "--models", "llama3:8b",
        ]), mock.patch("ollama_arena.cli.cmd_review_pr") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_list_subcommand(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", ["ollama-arena", "list"]), \
             mock.patch("ollama_arena.cli.cmd_list") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_leaderboard_subcommand(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", ["ollama-arena", "leaderboard"]), \
             mock.patch("ollama_arena.cli.cmd_leaderboard") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_web_subcommand(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", ["ollama-arena", "web"]), \
             mock.patch("ollama_arena.cli.cmd_web") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_sim_list_subcommand_calls_cmd_sim(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", ["ollama-arena", "sim", "list"]), \
             mock.patch("ollama_arena.cli.cmd_sim") as mock_cmd:
            main()
        mock_cmd.assert_called_once()
        args = mock_cmd.call_args.args[0]
        assert args.sim_cmd == "list"

    def test_sim_run_subcommand_parses_agents_and_ticks(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", [
            "ollama-arena", "sim", "run", "rps", "--agents", "a,b", "--ticks", "5",
        ]), mock.patch("ollama_arena.cli.cmd_sim") as mock_cmd:
            main()
        args = mock_cmd.call_args.args[0]
        assert args.sim_cmd == "run"
        assert args.scenario == "rps"
        assert args.agents == "a,b"
        assert args.ticks == 5

    def test_sim_train_subcommand_requires_run_id(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", ["ollama-arena", "sim", "train", "--run-id", "abc123"]), \
             mock.patch("ollama_arena.cli.cmd_sim") as mock_cmd:
            main()
        args = mock_cmd.call_args.args[0]
        assert args.run_id == "abc123"

    def test_sandbox_subcommand_calls_cmd_sandbox(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", ["ollama-arena", "sandbox", "list"]), \
             mock.patch("ollama_arena.cli.cmd_sandbox") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_swarm_subcommand_calls_cmd_swarm(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", ["ollama-arena", "swarm", "--task", "solve x"]), \
             mock.patch("ollama_arena.cli.cmd_swarm") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_redteam_subcommand_calls_cmd_redteam(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", [
            "ollama-arena", "redteam",
            "--attacker", "a", "--defender", "b", "--context", "ctx",
        ]), mock.patch("ollama_arena.cli.cmd_redteam") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_long_horizon_subcommand_calls_cmd_long_horizon(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", ["ollama-arena", "long-horizon", "list"]), \
             mock.patch("ollama_arena.cli.cmd_long_horizon") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_long_horizon_alias_lh(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", ["ollama-arena", "lh", "list"]), \
             mock.patch("ollama_arena.cli.cmd_long_horizon") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_node_subcommand_calls_cmd_node(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", ["ollama-arena", "node", "--status"]), \
             mock.patch("ollama_arena.cli.cmd_node") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_p2p_subcommand_calls_cmd_p2p(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", ["ollama-arena", "p2p", "--verify-result", "f.json"]), \
             mock.patch("ollama_arena.cli.cmd_p2p") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_import_subcommand(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", [
            "ollama-arena", "import", "--file", "data.csv",
        ]), mock.patch("ollama_arena.cli.cmd_import") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_export_subcommand(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", ["ollama-arena", "export"]), \
             mock.patch("ollama_arena.cli.cmd_export") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_results_subcommand(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", ["ollama-arena", "results"]), \
             mock.patch("ollama_arena.cli.cmd_results") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_perf_subcommand(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", ["ollama-arena", "perf"]), \
             mock.patch("ollama_arena.cli.cmd_perf") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_inspect_subcommand(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", [
            "ollama-arena", "inspect", "1",
        ]), mock.patch("ollama_arena.cli.cmd_inspect") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_report_subcommand(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", ["ollama-arena", "report"]), \
             mock.patch("ollama_arena.cli.cmd_report") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_publish_subcommand(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", [
            "ollama-arena", "publish",
        ]), mock.patch("ollama_arena.cli.cmd_publish") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_datasets_subcommand(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", ["ollama-arena", "datasets"]), \
             mock.patch("ollama_arena.cli.cmd_datasets") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_anti_leaderboard_subcommand(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", ["ollama-arena", "anti-leaderboard"]), \
             mock.patch("ollama_arena.cli.cmd_anti_leaderboard") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_tasks_subcommand(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", ["ollama-arena", "tasks"]), \
             mock.patch("ollama_arena.cli.cmd_tasks") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_finetune_subcommand(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", [
            "ollama-arena", "finetune", "--model", "llama3:8b", "--train", "data.jsonl",
        ]), mock.patch("ollama_arena.cli.cmd_finetune") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_genome_subcommand(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", [
            "ollama-arena", "genome", "scan",
        ]), mock.patch("ollama_arena.cli.cmd_genome") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_mcp_list_subcommand(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", ["ollama-arena", "mcp", "list"]), \
             mock.patch("ollama_arena.cli.cmd_mcp_list") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_mcp_diagnose_subcommand(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", ["ollama-arena", "mcp", "diagnose"]), \
             mock.patch("ollama_arena.cli.cmd_mcp_diagnose") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_mcp_enable_subcommand(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", ["ollama-arena", "mcp", "enable", "sqlite"]), \
             mock.patch("ollama_arena.cli.cmd_mcp_enable") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_mcp_disable_subcommand(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", ["ollama-arena", "mcp", "disable", "sqlite"]), \
             mock.patch("ollama_arena.cli.cmd_mcp_disable") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_mcp_install_subcommand(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", ["ollama-arena", "mcp", "install", "sqlite"]), \
             mock.patch("ollama_arena.cli.cmd_mcp_install") as mock_cmd:
            main()
        mock_cmd.assert_called_once()

    def test_global_db_flag(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", [
            "ollama-arena", "--db", "custom.db", "list",
        ]), mock.patch("ollama_arena.cli.cmd_list") as mock_cmd:
            main()
        args = mock_cmd.call_args[0][0]
        assert args.db == "custom.db"

    def test_global_backend_flag(self):
        from ollama_arena.cli import main
        with mock.patch("sys.argv", [
            "ollama-arena", "--backend", "openai", "list",
        ]), mock.patch("ollama_arena.cli.cmd_list") as mock_cmd:
            main()
        args = mock_cmd.call_args[0][0]
        assert args.backend == "openai"


class TestCmdWeb:
    def test_cmd_web_calls_run_web(self):
        from ollama_arena.cli.web_cmd import cmd_web
        args = mock.MagicMock()
        args.host = "0.0.0.0"
        args.port = 7860
        args.ollama = "http://localhost:11434"
        args.db = "arena.db"
        args.backend = None
        args.api_key = None
        with mock.patch("ollama_arena.web.run_web") as mock_run:
            cmd_web(args)
        mock_run.assert_called_once_with(
            host="0.0.0.0", port=7860,
            ollama_url="http://localhost:11434",
            db_path="arena.db",
            backend=None, api_key=None,
        )
