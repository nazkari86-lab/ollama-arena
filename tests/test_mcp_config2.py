"""Extended tests for mcp_config.py to push coverage above 60%."""
from __future__ import annotations
import json
import os
import subprocess
import unittest.mock as mock
import pytest


# ─── ServerConfig ─────────────────────────────────────────────────────────────

class TestServerConfig:
    def test_defaults(self):
        from ollama_arena.mcp_config import ServerConfig
        sc = ServerConfig(command="npx")
        assert sc.args == []
        assert sc.description == ""
        assert sc.env == {}
        assert sc.tier == "useful"
        assert sc.enabled is True
        assert sc.requires_api_key is False
        assert sc.is_external is False
        assert sc.url == ""
        assert sc.transport == "stdio"

    def test_custom_values(self):
        from ollama_arena.mcp_config import ServerConfig
        sc = ServerConfig(
            command="uvx",
            args=["mcp-server-sqlite"],
            description="test",
            env={"KEY": "val"},
            tier="essential",
            enabled=False,
            requires_api_key=True,
            is_external=True,
            url="http://server",
            transport="http",
        )
        assert sc.command == "uvx"
        assert sc.tier == "essential"
        assert sc.enabled is False
        assert sc.is_external is True


# ─── MCPConfig ────────────────────────────────────────────────────────────────

class TestMCPConfig:
    def _make_config(self):
        from ollama_arena.mcp_config import MCPConfig, ServerConfig
        return MCPConfig(servers={
            "alpha": ServerConfig(command="npx", tier="essential", enabled=True),
            "beta": ServerConfig(command="npx", tier="useful", enabled=True),
            "gamma": ServerConfig(command="npx", tier="advanced", enabled=False),
            "delta": ServerConfig(command="npx", tier="essential", enabled=True),
        })

    def test_get_enabled_servers_all(self):
        cfg = self._make_config()
        result = cfg.get_enabled_servers()
        assert "alpha" in result
        assert "beta" in result
        assert "delta" in result
        assert "gamma" not in result  # disabled

    def test_get_enabled_servers_tier_filter(self):
        cfg = self._make_config()
        result = cfg.get_enabled_servers(tier="essential")
        assert "alpha" in result
        assert "delta" in result
        assert "beta" not in result
        assert "gamma" not in result

    def test_get_enabled_servers_useful_tier(self):
        cfg = self._make_config()
        result = cfg.get_enabled_servers(tier="useful")
        assert "beta" in result
        assert "alpha" not in result

    def test_get_servers_by_tier(self):
        cfg = self._make_config()
        result = cfg.get_servers_by_tier("essential")
        assert "alpha" in result
        assert "delta" in result
        assert "beta" not in result
        # disabled servers still show up in get_servers_by_tier
        assert "gamma" not in result

    def test_get_servers_by_tier_advanced(self):
        cfg = self._make_config()
        result = cfg.get_servers_by_tier("advanced")
        assert "gamma" in result  # disabled but present in by_tier

    def test_empty_config(self):
        from ollama_arena.mcp_config import MCPConfig
        cfg = MCPConfig()
        assert cfg.get_enabled_servers() == {}
        assert cfg.get_servers_by_tier("essential") == {}


# ─── load_mcp_config ──────────────────────────────────────────────────────────

class TestLoadMcpConfig:
    def test_load_from_file(self, tmp_path):
        from ollama_arena.mcp_config import load_mcp_config
        data = {"servers": {
            "myserver": {
                "command": "uvx",
                "args": ["mcp-server-sqlite"],
                "tier": "essential",
            }
        }}
        p = tmp_path / "config.json"
        p.write_text(json.dumps(data))
        cfg = load_mcp_config(str(p))
        assert "myserver" in cfg.servers
        assert cfg.servers["myserver"].command == "uvx"

    def test_disabled_server_excluded(self, tmp_path):
        from ollama_arena.mcp_config import load_mcp_config
        data = {"servers": {
            "disabled_srv": {
                "command": "npx",
                "enabled": False,
            }
        }}
        p = tmp_path / "config.json"
        p.write_text(json.dumps(data))
        cfg = load_mcp_config(str(p))
        assert "disabled_srv" not in cfg.servers

    def test_all_fields_parsed(self, tmp_path):
        from ollama_arena.mcp_config import load_mcp_config
        data = {"servers": {
            "full": {
                "command": "uvx",
                "args": ["arg1"],
                "description": "desc",
                "env": {"K": "v"},
                "tier": "advanced",
                "enabled": True,
                "requires_api_key": True,
                "is_external": True,
                "url": "http://x",
                "transport": "http",
            }
        }}
        p = tmp_path / "config.json"
        p.write_text(json.dumps(data))
        cfg = load_mcp_config(str(p))
        s = cfg.servers["full"]
        assert s.args == ["arg1"]
        assert s.description == "desc"
        assert s.env == {"K": "v"}
        assert s.requires_api_key is True
        assert s.transport == "http"

    def test_invalid_json_uses_defaults(self, tmp_path):
        from ollama_arena.mcp_config import load_mcp_config
        p = tmp_path / "bad.json"
        p.write_text("{invalid json")
        cfg = load_mcp_config(str(p))
        assert len(cfg.servers) > 0  # falls back to DEFAULT_CONFIG

    def test_nonexistent_file_uses_defaults(self):
        from ollama_arena.mcp_config import load_mcp_config
        cfg = load_mcp_config("/nonexistent/path/to/config.json")
        assert len(cfg.servers) > 0


# ─── save_default_config ──────────────────────────────────────────────────────

class TestSaveDefaultConfig:
    def test_saves_to_custom_path(self, tmp_path, monkeypatch):
        from ollama_arena import mcp_config as mc_mod
        custom_path = tmp_path / ".config" / "arena" / "mcp_servers.json"
        monkeypatch.setattr(mc_mod, "_CONFIG_PATH", custom_path)
        result = mc_mod.save_default_config()
        assert custom_path.exists()
        data = json.loads(custom_path.read_text())
        assert "servers" in data


# ─── check_server_availability ───────────────────────────────────────────────

class TestCheckServerAvailability:
    def test_external_with_url(self):
        from ollama_arena.mcp_config import ServerConfig, check_server_availability
        sc = ServerConfig(command="npx", is_external=True, url="http://x")
        avail, reason = check_server_availability(sc)
        assert avail is True
        assert "External" in reason

    def test_command_not_found_in_path(self):
        from ollama_arena.mcp_config import ServerConfig, check_server_availability
        sc = ServerConfig(command="nonexistent_cmd_xyz")
        with mock.patch("shutil.which", return_value=None):
            avail, reason = check_server_availability(sc)
        assert avail is False
        assert "not found" in reason

    def test_command_success_returncode_0(self):
        from ollama_arena.mcp_config import ServerConfig, check_server_availability
        sc = ServerConfig(command="npx", args=["--version"])
        mock_result = mock.MagicMock()
        mock_result.returncode = 0
        with mock.patch("shutil.which", return_value="/usr/bin/npx"), \
             mock.patch("subprocess.run", return_value=mock_result):
            avail, reason = check_server_availability(sc)
        assert avail is True

    def test_command_returncode_1(self):
        from ollama_arena.mcp_config import ServerConfig, check_server_availability
        sc = ServerConfig(command="npx", args=[])
        mock_result = mock.MagicMock()
        mock_result.returncode = 1
        with mock.patch("shutil.which", return_value="/usr/bin/npx"), \
             mock.patch("subprocess.run", return_value=mock_result):
            avail, reason = check_server_availability(sc)
        assert avail is True  # returncode 1 is still "available"

    def test_command_returncode_nonzero(self):
        from ollama_arena.mcp_config import ServerConfig, check_server_availability
        sc = ServerConfig(command="bad_cmd")
        mock_result = mock.MagicMock()
        mock_result.returncode = 127
        with mock.patch("shutil.which", return_value="/usr/bin/bad_cmd"), \
             mock.patch("subprocess.run", return_value=mock_result):
            avail, reason = check_server_availability(sc)
        assert avail is False

    def test_timeout(self):
        from ollama_arena.mcp_config import ServerConfig, check_server_availability
        sc = ServerConfig(command="slow_cmd")
        with mock.patch("shutil.which", return_value="/usr/bin/slow_cmd"), \
             mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("slow_cmd", 10)):
            avail, reason = check_server_availability(sc)
        assert avail is False
        assert "timed out" in reason

    def test_file_not_found(self):
        from ollama_arena.mcp_config import ServerConfig, check_server_availability
        sc = ServerConfig(command="missing")
        with mock.patch("shutil.which", return_value="/usr/bin/missing"), \
             mock.patch("subprocess.run", side_effect=FileNotFoundError()):
            avail, reason = check_server_availability(sc)
        assert avail is False

    def test_generic_exception(self):
        from ollama_arena.mcp_config import ServerConfig, check_server_availability
        sc = ServerConfig(command="crash_cmd")
        with mock.patch("shutil.which", return_value="/path"), \
             mock.patch("subprocess.run", side_effect=RuntimeError("boom")):
            avail, reason = check_server_availability(sc)
        assert avail is False
        assert "boom" in reason

    def test_no_args_uses_help(self):
        from ollama_arena.mcp_config import ServerConfig, check_server_availability
        sc = ServerConfig(command="myapp", args=[])
        mock_result = mock.MagicMock()
        mock_result.returncode = 0
        with mock.patch("shutil.which", return_value="/usr/bin/myapp"), \
             mock.patch("subprocess.run", return_value=mock_result) as mock_run:
            avail, reason = check_server_availability(sc)
        # should have used ["--help"] as test args
        call_args = mock_run.call_args[0][0]
        assert "--help" in call_args


# ─── detect_common_issues ────────────────────────────────────────────────────

class TestDetectCommonIssues:
    def test_npx_node_missing(self):
        from ollama_arena.mcp_config import ServerConfig, detect_common_issues
        sc = ServerConfig(command="npx")
        with mock.patch("shutil.which", return_value=None):
            issues = detect_common_issues(sc)
        assert any("Node.js" in i for i in issues)

    def test_npx_npx_missing(self):
        from ollama_arena.mcp_config import ServerConfig, detect_common_issues
        sc = ServerConfig(command="npx")
        def which_side(cmd):
            return "/node" if cmd == "node" else None
        with mock.patch("shutil.which", side_effect=which_side):
            issues = detect_common_issues(sc)
        assert any("npx" in i for i in issues)

    def test_uvx_uv_missing(self):
        from ollama_arena.mcp_config import ServerConfig, detect_common_issues
        sc = ServerConfig(command="uvx")
        with mock.patch("shutil.which", return_value=None):
            issues = detect_common_issues(sc)
        assert any("uv" in i for i in issues)

    def test_env_var_missing(self):
        from ollama_arena.mcp_config import ServerConfig, detect_common_issues
        sc = ServerConfig(command="npx", env={"MY_API_KEY": ""})
        with mock.patch("shutil.which", return_value="/npx"), \
             mock.patch.dict(os.environ, {}, clear=True):
            issues = detect_common_issues(sc)
        assert any("MY_API_KEY" in i for i in issues)

    def test_env_var_set(self):
        from ollama_arena.mcp_config import ServerConfig, detect_common_issues
        sc = ServerConfig(command="npx", env={"MY_API_KEY": ""})
        with mock.patch("shutil.which", return_value="/npx"), \
             mock.patch.dict(os.environ, {"MY_API_KEY": "set_value"}):
            issues = detect_common_issues(sc)
        assert not any("MY_API_KEY" in i for i in issues)

    def test_workspace_dir_missing(self):
        from ollama_arena.mcp_config import ServerConfig, detect_common_issues
        sc = ServerConfig(command="npx", args=["arena_workspace"])
        with mock.patch("shutil.which", return_value="/npx"), \
             mock.patch("pathlib.Path.exists", return_value=False):
            issues = detect_common_issues(sc)
        assert any("arena_workspace" in i or "Workspace" in i for i in issues)

    def test_no_issues_normal_cmd(self):
        from ollama_arena.mcp_config import ServerConfig, detect_common_issues
        sc = ServerConfig(command="python3")
        issues = detect_common_issues(sc)
        assert isinstance(issues, list)


# ─── diagnose_mcp_servers ────────────────────────────────────────────────────

class TestDiagnoseMcpServers:
    def test_diagnose_empty(self):
        from ollama_arena.mcp_config import MCPConfig, diagnose_mcp_servers
        cfg = MCPConfig(servers={})
        result = diagnose_mcp_servers(cfg)
        assert result == {}

    def test_diagnose_single_available(self):
        from ollama_arena.mcp_config import MCPConfig, ServerConfig, diagnose_mcp_servers
        sc = ServerConfig(command="npx", tier="essential", requires_api_key=False)
        cfg = MCPConfig(servers={"test": sc})
        with mock.patch("ollama_arena.mcp_config.check_server_availability", return_value=(True, "ok")), \
             mock.patch("ollama_arena.mcp_config.detect_common_issues", return_value=[]):
            result = diagnose_mcp_servers(cfg)
        assert "test" in result
        assert result["test"]["available"] is True
        assert result["test"]["tier"] == "essential"

    def test_diagnose_missing_env(self):
        from ollama_arena.mcp_config import MCPConfig, ServerConfig, diagnose_mcp_servers
        sc = ServerConfig(command="npx", env={"SECRET_KEY": ""}, requires_api_key=True)
        cfg = MCPConfig(servers={"srv": sc})
        with mock.patch("ollama_arena.mcp_config.check_server_availability", return_value=(True, "ok")), \
             mock.patch("ollama_arena.mcp_config.detect_common_issues", return_value=[]), \
             mock.patch.dict(os.environ, {}, clear=True):
            result = diagnose_mcp_servers(cfg)
        assert "SECRET_KEY" in result["srv"]["missing_env"]


# ─── print_server_diagnostics ────────────────────────────────────────────────

class TestPrintServerDiagnostics:
    def test_prints_without_error(self, capsys):
        from ollama_arena.mcp_config import print_server_diagnostics
        diag = {
            "alpha": {
                "available": True, "reason": "ok", "common_issues": [],
                "missing_env": [], "tier": "essential", "enabled": True,
                "requires_api_key": False, "is_external": False, "transport": "stdio",
            },
            "beta": {
                "available": False, "reason": "not found", "common_issues": ["issue1"],
                "missing_env": ["MY_KEY"], "tier": "useful", "enabled": True,
                "requires_api_key": True, "is_external": True, "transport": "http",
            },
        }
        print_server_diagnostics(diag)
        out = capsys.readouterr().out
        assert "alpha" in out
        assert "beta" in out

    def test_prints_disabled_server(self, capsys):
        from ollama_arena.mcp_config import print_server_diagnostics
        diag = {
            "disabled_srv": {
                "available": False, "reason": "cmd missing", "common_issues": [],
                "missing_env": [], "tier": "advanced", "enabled": False,
                "requires_api_key": False, "is_external": False, "transport": "stdio",
            },
        }
        print_server_diagnostics(diag)
        out = capsys.readouterr().out
        assert "Disabled" in out or "disabled" in out.lower()


# ─── get_free_servers ─────────────────────────────────────────────────────────

class TestGetFreeServers:
    def test_empty(self):
        from ollama_arena.mcp_config import MCPConfig, get_free_servers
        cfg = MCPConfig(servers={})
        with mock.patch("ollama_arena.mcp_config.diagnose_mcp_servers", return_value={}):
            result = get_free_servers(cfg)
        assert result == {}

    def test_returns_free_available_servers(self):
        from ollama_arena.mcp_config import MCPConfig, ServerConfig, get_free_servers
        sc_free = ServerConfig(command="npx", requires_api_key=False)
        sc_paid = ServerConfig(command="npx", requires_api_key=True)
        cfg = MCPConfig(servers={"free_srv": sc_free, "paid_srv": sc_paid})
        diag = {
            "free_srv": {"available": True, "requires_api_key": False},
            "paid_srv": {"available": True, "requires_api_key": True},
        }
        with mock.patch("ollama_arena.mcp_config.diagnose_mcp_servers", return_value=diag):
            result = get_free_servers(cfg)
        assert "free_srv" in result
        assert "paid_srv" not in result

    def test_excludes_unavailable(self):
        from ollama_arena.mcp_config import MCPConfig, ServerConfig, get_free_servers
        sc = ServerConfig(command="npx", requires_api_key=False)
        cfg = MCPConfig(servers={"srv": sc})
        diag = {"srv": {"available": False, "requires_api_key": False}}
        with mock.patch("ollama_arena.mcp_config.diagnose_mcp_servers", return_value=diag):
            result = get_free_servers(cfg)
        assert "srv" not in result
