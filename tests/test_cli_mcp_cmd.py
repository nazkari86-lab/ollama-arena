"""Tests for cli/mcp_cmd.py."""
from __future__ import annotations
import json
import unittest.mock as mock
import pytest


def _mock_console():
    return mock.MagicMock()


def _make_args(**kwargs):
    args = mock.MagicMock()
    args.config = None
    args.server = "sqlite"
    for k, v in kwargs.items():
        setattr(args, k, v)
    return args


def _make_server_config(name="sqlite", enabled=True, tier="essential", requires_api_key=False):
    from ollama_arena.mcp_config import ServerConfig
    return ServerConfig(
        command="uvx",
        args=["mcp-server-sqlite"],
        description="SQLite MCP server",
        tier=tier,
        enabled=enabled,
        requires_api_key=requires_api_key,
    )


def _make_mcp_config():
    from ollama_arena.mcp_config import MCPConfig, ServerConfig
    servers = {
        "sqlite": _make_server_config("sqlite", enabled=True, tier="essential"),
        "memory": ServerConfig(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-memory"],
            description="In-memory storage",
            tier="useful",
            enabled=False,
            requires_api_key=False,
        ),
    }
    return MCPConfig(servers=servers)


class TestCmdMcpList:
    def test_lists_all_servers(self):
        from ollama_arena.cli.mcp_cmd import cmd_mcp_list
        args = _make_args()
        mock_c = _mock_console()
        config = _make_mcp_config()

        with mock.patch("ollama_arena.cli.mcp_cmd._console", return_value=mock_c), \
             mock.patch("ollama_arena.mcp_config.load_mcp_config", return_value=config):
            cmd_mcp_list(args)

        assert mock_c.print.called

    def test_unknown_tier_does_not_crash(self):
        """A server config with a tier outside essential/useful/advanced (e.g. from a
        hand-edited --config file) must not raise KeyError; it should fall back to a
        default icon instead of crashing the whole `mcp list` command."""
        from ollama_arena.cli.mcp_cmd import cmd_mcp_list
        from ollama_arena.mcp_config import MCPConfig
        args = _make_args()
        mock_c = _mock_console()
        config = MCPConfig(servers={"weird": _make_server_config("weird", tier="not_a_real_tier")})

        with mock.patch("ollama_arena.cli.mcp_cmd._console", return_value=mock_c), \
             mock.patch("ollama_arena.mcp_config.load_mcp_config", return_value=config):
            cmd_mcp_list(args)  # must not raise

        assert mock_c.print.called

    def test_with_env_variables(self):
        from ollama_arena.cli.mcp_cmd import cmd_mcp_list
        from ollama_arena.mcp_config import MCPConfig, ServerConfig
        args = _make_args()
        mock_c = _mock_console()

        server = ServerConfig(
            command="npx",
            args=["-y", "some-server"],
            description="Has env",
            tier="advanced",
            enabled=True,
            requires_api_key=True,
            env={"API_KEY": "secret"},
        )
        config = MCPConfig(servers={"some_server": server})

        with mock.patch("ollama_arena.cli.mcp_cmd._console", return_value=mock_c), \
             mock.patch("ollama_arena.mcp_config.load_mcp_config", return_value=config):
            cmd_mcp_list(args)

        assert mock_c.print.called


class TestCmdMcpDiagnose:
    def test_diagnose_runs(self):
        from ollama_arena.cli.mcp_cmd import cmd_mcp_diagnose
        args = _make_args()
        mock_c = _mock_console()
        config = _make_mcp_config()

        mock_diag_results = {"sqlite": {"available": True, "issues": []}}
        mock_free_servers = {"sqlite": _make_server_config()}

        with mock.patch("ollama_arena.cli.mcp_cmd._console", return_value=mock_c), \
             mock.patch("ollama_arena.mcp_config.load_mcp_config", return_value=config), \
             mock.patch("ollama_arena.mcp_config.diagnose_mcp_servers", return_value=mock_diag_results), \
             mock.patch("ollama_arena.mcp_config.print_server_diagnostics"), \
             mock.patch("ollama_arena.mcp_config.get_free_servers", return_value=mock_free_servers), \
             mock.patch("ollama_arena.cli.mcp_cmd.print_success") as mock_ps:
            cmd_mcp_diagnose(args)

        mock_ps.assert_called()
        assert mock_c.print.called


class TestCmdMcpEnable:
    def test_enable_existing_server(self, tmp_path):
        from ollama_arena.cli.mcp_cmd import cmd_mcp_enable
        args = _make_args(server="sqlite")
        config = _make_mcp_config()
        config.servers["sqlite"].enabled = False  # start disabled

        fake_config_path = tmp_path / "mcp.json"

        with mock.patch("ollama_arena.mcp_config.load_mcp_config", return_value=config), \
             mock.patch("ollama_arena.mcp_config._CONFIG_PATH", fake_config_path), \
             mock.patch("ollama_arena.cli.mcp_cmd.print_success") as mock_ps, \
             mock.patch("ollama_arena.cli.mcp_cmd.print_error") as mock_pe:
            cmd_mcp_enable(args)

        mock_ps.assert_called_once()
        mock_pe.assert_not_called()
        # Verify enabled flag was set
        assert config.servers["sqlite"].enabled is True

    def test_enable_nonexistent_server(self, tmp_path):
        from ollama_arena.cli.mcp_cmd import cmd_mcp_enable
        args = _make_args(server="nonexistent")
        config = _make_mcp_config()

        with mock.patch("ollama_arena.mcp_config.load_mcp_config", return_value=config), \
             mock.patch("ollama_arena.cli.mcp_cmd.print_success") as mock_ps, \
             mock.patch("ollama_arena.cli.mcp_cmd.print_error") as mock_pe:
            cmd_mcp_enable(args)

        mock_pe.assert_called_once()
        mock_ps.assert_not_called()


class TestCmdMcpDisable:
    def test_disable_existing_server(self, tmp_path):
        from ollama_arena.cli.mcp_cmd import cmd_mcp_disable
        args = _make_args(server="sqlite")
        config = _make_mcp_config()
        config.servers["sqlite"].enabled = True  # start enabled

        fake_config_path = tmp_path / "mcp.json"

        with mock.patch("ollama_arena.mcp_config.load_mcp_config", return_value=config), \
             mock.patch("ollama_arena.mcp_config._CONFIG_PATH", fake_config_path), \
             mock.patch("ollama_arena.cli.mcp_cmd.print_success") as mock_ps, \
             mock.patch("ollama_arena.cli.mcp_cmd.print_error") as mock_pe:
            cmd_mcp_disable(args)

        mock_ps.assert_called_once()
        mock_pe.assert_not_called()
        assert config.servers["sqlite"].enabled is False

    def test_disable_nonexistent_server(self):
        from ollama_arena.cli.mcp_cmd import cmd_mcp_disable
        args = _make_args(server="unknown")
        config = _make_mcp_config()

        with mock.patch("ollama_arena.mcp_config.load_mcp_config", return_value=config), \
             mock.patch("ollama_arena.cli.mcp_cmd.print_error") as mock_pe:
            cmd_mcp_disable(args)

        mock_pe.assert_called_once()


class TestCmdMcpInstall:
    def test_install_known_server_success(self):
        from ollama_arena.cli.mcp_cmd import cmd_mcp_install
        args = _make_args(server="sqlite")
        mock_c = _mock_console()

        mock_result = mock.MagicMock()
        mock_result.returncode = 0

        with mock.patch("ollama_arena.cli.mcp_cmd._console", return_value=mock_c), \
             mock.patch("subprocess.run", return_value=mock_result) as mock_run, \
             mock.patch("ollama_arena.cli.mcp_cmd.print_success") as mock_ps:
            cmd_mcp_install(args)

        mock_run.assert_called_once()
        mock_ps.assert_called_once()

    def test_install_timeout_does_not_crash(self):
        """subprocess.run must be bounded with a timeout; a hang (e.g. npx waiting
        on a network prompt) should produce a clean error, not an indefinite hang
        or an uncaught TimeoutExpired traceback."""
        from ollama_arena.cli.mcp_cmd import cmd_mcp_install
        import subprocess
        args = _make_args(server="sqlite")
        mock_c = _mock_console()

        with mock.patch("ollama_arena.cli.mcp_cmd._console", return_value=mock_c), \
             mock.patch("subprocess.run",
                        side_effect=subprocess.TimeoutExpired(cmd="uvx", timeout=120)) as mock_run, \
             mock.patch("ollama_arena.cli.mcp_cmd.print_error") as mock_pe:
            cmd_mcp_install(args)  # must not raise

        mock_run.assert_called_once()
        # timeout kwarg must actually be passed through to subprocess.run
        assert mock_run.call_args.kwargs.get("timeout") == 120
        mock_pe.assert_called_once()
        assert "timed out" in mock_pe.call_args[0][0].lower()

    def test_install_known_server_failure(self):
        from ollama_arena.cli.mcp_cmd import cmd_mcp_install
        import subprocess
        args = _make_args(server="memory")
        mock_c = _mock_console()

        with mock.patch("ollama_arena.cli.mcp_cmd._console", return_value=mock_c), \
             mock.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "npx", stderr="error")) as mock_run, \
             mock.patch("ollama_arena.cli.mcp_cmd.print_error") as mock_pe:
            cmd_mcp_install(args)

        mock_pe.assert_called_once()

    def test_install_unknown_server(self):
        from ollama_arena.cli.mcp_cmd import cmd_mcp_install
        args = _make_args(server="nonexistent_server_xyz")
        mock_c = _mock_console()

        with mock.patch("ollama_arena.cli.mcp_cmd._console", return_value=mock_c), \
             mock.patch("ollama_arena.cli.mcp_cmd.print_error") as mock_pe:
            cmd_mcp_install(args)

        mock_pe.assert_called_once()

    def test_install_git_server(self):
        from ollama_arena.cli.mcp_cmd import cmd_mcp_install
        args = _make_args(server="git")
        mock_c = _mock_console()
        mock_result = mock.MagicMock()

        with mock.patch("ollama_arena.cli.mcp_cmd._console", return_value=mock_c), \
             mock.patch("subprocess.run", return_value=mock_result) as mock_run, \
             mock.patch("ollama_arena.cli.mcp_cmd.print_success"):
            cmd_mcp_install(args)

        mock_run.assert_called_once()

    def test_install_filesystem_server(self):
        from ollama_arena.cli.mcp_cmd import cmd_mcp_install
        args = _make_args(server="filesystem")
        mock_c = _mock_console()
        mock_result = mock.MagicMock()

        with mock.patch("ollama_arena.cli.mcp_cmd._console", return_value=mock_c), \
             mock.patch("subprocess.run", return_value=mock_result), \
             mock.patch("ollama_arena.cli.mcp_cmd.print_success"):
            cmd_mcp_install(args)

    def test_install_time_server(self):
        from ollama_arena.cli.mcp_cmd import cmd_mcp_install
        args = _make_args(server="time")
        mock_c = _mock_console()
        mock_result = mock.MagicMock()

        with mock.patch("ollama_arena.cli.mcp_cmd._console", return_value=mock_c), \
             mock.patch("subprocess.run", return_value=mock_result), \
             mock.patch("ollama_arena.cli.mcp_cmd.print_success"):
            cmd_mcp_install(args)
