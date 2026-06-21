"""Tests for mcp/tools/* — workspace, git, network, dev, data, browser, computer."""
from __future__ import annotations

import json
import unittest.mock as mock
import pytest


# ──────────────────────────────────────────────────────────────────────────────
# workspace tools
# ──────────────────────────────────────────────────────────────────────────────

class TestWorkspaceTools:
    def test_safe_path_normal(self):
        from ollama_arena.mcp.tools.workspace import _safe_path, WORKSPACE_DIR
        p = _safe_path("subdir/file.txt")
        assert str(p).startswith(str(WORKSPACE_DIR))

    def test_safe_path_root(self):
        from ollama_arena.mcp.tools.workspace import _safe_path, WORKSPACE_DIR
        p = _safe_path(".")
        assert p == WORKSPACE_DIR.resolve()

    def test_safe_path_leading_slash_stripped(self):
        from ollama_arena.mcp.tools.workspace import _safe_path, WORKSPACE_DIR
        p = _safe_path("/subdir/file.txt")
        assert str(p).startswith(str(WORKSPACE_DIR))

    def test_safe_path_escape_raises(self):
        from ollama_arena.mcp.tools.workspace import _safe_path, SecurityError
        with pytest.raises(SecurityError):
            _safe_path("../../etc/passwd")

    def test_safe_path_blocks_sibling_prefix_bypass(self, tmp_path):
        """A sibling directory whose name merely starts with the workspace dir's
        name (e.g. 'arena_workspace_evil') must NOT pass containment checks just
        because str.startswith() matched on the path prefix."""
        from ollama_arena.mcp.tools import workspace as ws_mod

        workspace = tmp_path / "arena_workspace"
        workspace.mkdir()
        sibling_evil = tmp_path / "arena_workspace_evil"
        sibling_evil.mkdir()
        (sibling_evil / "secret.txt").write_text("leaked")

        with mock.patch.object(ws_mod, "WORKSPACE_DIR", workspace):
            # Old buggy check (string prefix) would have classified this as inside
            # the workspace because str(sibling) starts with str(workspace).
            target = sibling_evil / "secret.txt"
            root = workspace.resolve()
            old_buggy_check_would_allow = str(target.resolve()).startswith(str(root))
            assert old_buggy_check_would_allow  # sanity: confirms the bypass shape is real

            # The real _safe_path always joins WORKSPACE_DIR/rel, so traversal must
            # go through ".." — verify that still resolves outside and is rejected.
            with pytest.raises(ws_mod.SecurityError):
                ws_mod._safe_path("../arena_workspace_evil/secret.txt")

    def test_safe_path_root_is_relative_check_not_string_prefix(self):
        """Regression for the startswith() bypass: verify the containment check
        is implemented via Path.parents membership, not string prefix matching."""
        import inspect
        from ollama_arena.mcp.tools import workspace as ws_mod

        source = inspect.getsource(ws_mod._safe_path)
        assert "startswith" not in source

    def test_ls_nonexistent_returns_error(self):
        from ollama_arena.mcp.tools.workspace import ls
        result = ls({"path": "definitely_nonexistent_xyz_path_12345"})
        assert "Error" in result or "not found" in result.lower()

    def test_ls_existing_dir(self):
        from ollama_arena.mcp.tools.workspace import ls, WORKSPACE_DIR
        WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
        result = ls({"path": "."})
        assert isinstance(result, str)

    def test_read_file_nonexistent(self):
        from ollama_arena.mcp.tools.workspace import read_file
        result = read_file({"path": "nonexistent_file_xyz.txt"})
        assert "Error" in result or "not found" in result.lower()

    def test_write_and_read_file(self, tmp_path):
        from ollama_arena.mcp.tools.workspace import write_file, read_file, WORKSPACE_DIR
        test_file = "test_write_read.txt"
        with mock.patch("ollama_arena.mcp.tools.workspace.WORKSPACE_DIR", tmp_path):
            write_result = write_file({"path": test_file, "content": "hello world"})
            assert "hello world" not in write_result  # returns byte count
            assert "Wrote" in write_result
            read_result = read_file({"path": test_file})
            assert read_result == "hello world"

    def test_write_file_escape_prevented(self):
        from ollama_arena.mcp.tools.workspace import write_file
        result = write_file({"path": "../../evil.txt", "content": "bad"})
        assert "Error" in result

    def test_ls_returns_file_name_for_file(self, tmp_path):
        from ollama_arena.mcp.tools.workspace import ls, WORKSPACE_DIR
        with mock.patch("ollama_arena.mcp.tools.workspace.WORKSPACE_DIR", tmp_path):
            (tmp_path / "solo.txt").write_text("x")
            result = ls({"path": "solo.txt"})
            assert "solo.txt" in result

    def test_tool_defs_returns_list(self):
        from ollama_arena.mcp.tools.workspace import tool_defs
        defs = tool_defs()
        assert len(defs) == 3
        names = [d[0] for d in defs]
        assert "ls" in names
        assert "read_file" in names
        assert "write_file" in names


# ──────────────────────────────────────────────────────────────────────────────
# git tools
# ──────────────────────────────────────────────────────────────────────────────

class TestGitTools:
    def test_git_status_success(self):
        from ollama_arena.mcp.tools.git import git_status
        mock_result = mock.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "M  file.py\n"
        with mock.patch("subprocess.run", return_value=mock_result):
            result = git_status({})
        assert "file.py" in result

    def test_git_status_error(self):
        from ollama_arena.mcp.tools.git import git_status
        mock_result = mock.MagicMock()
        mock_result.returncode = 128
        mock_result.stderr = "not a git repo"
        mock_result.stdout = ""
        with mock.patch("subprocess.run", return_value=mock_result):
            result = git_status({})
        assert "Git error" in result

    def test_git_status_exception(self):
        from ollama_arena.mcp.tools.git import git_status
        with mock.patch("subprocess.run", side_effect=OSError("no git")):
            result = git_status({})
        assert "Error" in result

    def test_git_commit_no_message(self):
        from ollama_arena.mcp.tools.git import git_commit
        result = git_commit({"message": ""})
        assert "Error" in result

    def test_git_commit_success(self):
        from ollama_arena.mcp.tools.git import git_commit
        add_result = mock.MagicMock()
        add_result.returncode = 0
        add_result.stdout = ""
        commit_result = mock.MagicMock()
        commit_result.returncode = 0
        commit_result.stdout = "[main abc123] test commit"
        with mock.patch("subprocess.run", side_effect=[add_result, commit_result]):
            result = git_commit({"message": "test commit"})
        assert "abc123" in result or "main" in result

    def test_git_commit_add_fails(self):
        from ollama_arena.mcp.tools.git import git_commit
        add_result = mock.MagicMock()
        add_result.returncode = 1
        add_result.stderr = "permission denied"
        add_result.stdout = ""
        with mock.patch("subprocess.run", return_value=add_result):
            result = git_commit({"message": "test"})
        assert "Git error" in result

    def test_tool_defs_returns_two(self):
        from ollama_arena.mcp.tools.git import tool_defs
        defs = tool_defs()
        assert len(defs) == 2
        names = [d[0] for d in defs]
        assert "git_status" in names
        assert "git_commit" in names


# ──────────────────────────────────────────────────────────────────────────────
# network tools
# ──────────────────────────────────────────────────────────────────────────────

class TestNetworkTools:
    def test_get_datetime_returns_time(self):
        from ollama_arena.mcp.tools.network import get_datetime
        result = get_datetime({})
        assert "Current time:" in result
        assert "2026" in result or "202" in result

    def test_system_info_returns_os(self):
        from ollama_arena.mcp.tools.network import system_info
        result = system_info({})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_ip_info_success(self):
        from ollama_arena.mcp.tools.network import ip_info
        mock_resp = mock.MagicMock()
        mock_resp.json.return_value = {
            "ip": "1.2.3.4", "city": "Almaty",
            "country_name": "Kazakhstan", "org": "Telecom",
        }
        mock_resp.raise_for_status = mock.MagicMock()
        with mock.patch("requests.get", return_value=mock_resp):
            result = ip_info({})
        assert "1.2.3.4" in result
        assert "Almaty" in result

    def test_ip_info_request_error(self):
        from ollama_arena.mcp.tools.network import ip_info
        with mock.patch("requests.get", side_effect=Exception("timeout")):
            result = ip_info({})
        assert "Error" in result

    def test_ping_no_host(self):
        from ollama_arena.mcp.tools.network import ping
        result = ping({})
        assert "Error" in result

    def test_ping_success(self):
        from ollama_arena.mcp.tools.network import ping
        mock_result = mock.MagicMock()
        mock_result.stdout = "64 bytes from 8.8.8.8: time=5ms"
        mock_result.stderr = ""
        with mock.patch("subprocess.run", return_value=mock_result):
            result = ping({"host": "8.8.8.8", "count": 1})
        assert "8.8.8.8" in result

    def test_ping_exception(self):
        from ollama_arena.mcp.tools.network import ping
        with mock.patch("subprocess.run", side_effect=OSError("no ping")):
            result = ping({"host": "bad_host"})
        assert "Error" in result

    def test_tool_defs_count(self):
        from ollama_arena.mcp.tools.network import tool_defs
        defs = tool_defs()
        assert len(defs) == 4


# ──────────────────────────────────────────────────────────────────────────────
# dev tools
# ──────────────────────────────────────────────────────────────────────────────

class TestDevTools:
    def test_codebase_search_no_pattern(self):
        from ollama_arena.mcp.tools.dev import codebase_search
        result = codebase_search({})
        assert "Error" in result

    def test_codebase_search_success(self):
        from ollama_arena.mcp.tools.dev import codebase_search
        mock_result = mock.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "file.py:10: def foo():\n"
        with mock.patch("subprocess.run", return_value=mock_result):
            result = codebase_search({"pattern": "def foo"})
        assert "def foo" in result

    def test_codebase_search_no_match(self):
        from ollama_arena.mcp.tools.dev import codebase_search
        mock_result = mock.MagicMock()
        mock_result.returncode = 1
        with mock.patch("subprocess.run", return_value=mock_result):
            result = codebase_search({"pattern": "xyz_nonexistent"})
        assert "No matches" in result

    def test_codebase_search_exception(self):
        from ollama_arena.mcp.tools.dev import codebase_search
        with mock.patch("subprocess.run", side_effect=OSError("grep failed")):
            result = codebase_search({"pattern": "test"})
        assert "error" in result.lower()

    def test_ast_parse_missing_file(self):
        from ollama_arena.mcp.tools.dev import ast_parse
        result = ast_parse({"file_path": "nonexistent_file_xyz.py"})
        assert "Error" in result

    def test_ast_parse_escape(self):
        from ollama_arena.mcp.tools.dev import ast_parse
        result = ast_parse({"file_path": "../../etc/hosts"})
        assert "Error" in result

    def test_ast_parse_valid_file(self, tmp_path):
        from ollama_arena.mcp.tools.dev import ast_parse
        from ollama_arena.mcp.tools.workspace import WORKSPACE_DIR
        with mock.patch("ollama_arena.mcp.tools.workspace.WORKSPACE_DIR", tmp_path):
            (tmp_path / "test_mod.py").write_text("def hello():\n    pass\nclass MyClass:\n    pass")
            result = ast_parse({"file_path": "test_mod.py"})
        data = json.loads(result)
        assert "hello" in data["functions"]
        assert "MyClass" in data["classes"]

    def test_consult_expert_debugging(self):
        from ollama_arena.mcp.tools.dev import consult_expert
        result = consult_expert({"topic": "debugging techniques"})
        assert "Debugging" in result or "debug" in result.lower()

    def test_consult_expert_unknown(self):
        from ollama_arena.mcp.tools.dev import consult_expert
        result = consult_expert({"topic": "quantum_computing_xyz"})
        assert "Available" in result

    def test_consult_expert_tdd(self):
        from ollama_arena.mcp.tools.dev import consult_expert
        result = consult_expert({"topic": "tdd best practices"})
        assert "TDD" in result or "Red-Green" in result

    def test_consult_expert_security(self):
        from ollama_arena.mcp.tools.dev import consult_expert
        result = consult_expert({"topic": "security review"})
        assert "Security" in result or "security" in result.lower()

    def test_algo_docs_binary_search(self):
        from ollama_arena.mcp.tools.dev import algo_docs
        with mock.patch("ollama_arena.mcp.tools.dev.ddg_search", return_value="search result"):
            result = algo_docs({"topic": "binary search algorithm"})
        assert "Binary Search" in result or "O(log n)" in result

    def test_algo_docs_unknown_uses_search(self):
        from ollama_arena.mcp.tools.dev import algo_docs
        with mock.patch("ollama_arena.mcp.tools.dev.ddg_search", return_value="web result") as m:
            result = algo_docs({"topic": "unknown_algorithm_xyz"})
        assert result == "web result"
        m.assert_called_once()

    def test_ui_tars_action(self):
        from ollama_arena.mcp.tools.dev import ui_tars_action
        result = ui_tars_action({"action": "click", "target": "button"})
        assert "click" in result.lower()
        assert "button" in result

    def test_tool_defs_count(self):
        from ollama_arena.mcp.tools.dev import tool_defs
        defs = tool_defs()
        assert len(defs) == 5


# ──────────────────────────────────────────────────────────────────────────────
# data tools
# ──────────────────────────────────────────────────────────────────────────────

class TestDataTools:
    def test_math_solver_addition(self):
        from ollama_arena.mcp.tools.data import math_solver
        result = math_solver({"expression": "3 + 4"})
        assert "7" in result

    def test_math_solver_complex(self):
        from ollama_arena.mcp.tools.data import math_solver
        result = math_solver({"expression": "2 ** 10"})
        assert "1024" in result

    def test_math_solver_empty(self):
        from ollama_arena.mcp.tools.data import math_solver
        result = math_solver({})
        assert "Error" in result

    def test_math_solver_division_by_zero(self):
        from ollama_arena.mcp.tools.data import math_solver
        result = math_solver({"expression": "1 / 0"})
        assert "Error" in result

    def test_math_solver_sqrt(self):
        from ollama_arena.mcp.tools.data import math_solver
        result = math_solver({"expression": "sqrt(16)"})
        assert "4" in result

    def test_math_solver_unsupported_expr(self):
        from ollama_arena.mcp.tools.data import math_solver
        result = math_solver({"expression": "import os"})
        assert "Error" in result

    def test_math_solver_negative(self):
        from ollama_arena.mcp.tools.data import math_solver
        result = math_solver({"expression": "-5 + 3"})
        assert "-2" in result

    def test_crypto_price_success(self):
        from ollama_arena.mcp.tools.data import crypto_price
        mock_resp = mock.MagicMock()
        mock_resp.json.return_value = {"bitcoin": {"usd": 50000.0}}
        mock_resp.raise_for_status = mock.MagicMock()
        with mock.patch("requests.get", return_value=mock_resp):
            result = crypto_price({"coin": "bitcoin"})
        assert "50,000.00" in result or "50000" in result

    def test_crypto_price_unknown_coin(self):
        from ollama_arena.mcp.tools.data import crypto_price
        mock_resp = mock.MagicMock()
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = mock.MagicMock()
        with mock.patch("requests.get", return_value=mock_resp):
            result = crypto_price({"coin": "nonexistent_coin_xyz"})
        assert "Error" in result or "Unknown" in result

    def test_crypto_price_exception(self):
        from ollama_arena.mcp.tools.data import crypto_price
        with mock.patch("requests.get", side_effect=Exception("network error")):
            result = crypto_price({"coin": "bitcoin"})
        assert "Error" in result

    def test_tool_defs_returns_two(self):
        from ollama_arena.mcp.tools.data import tool_defs
        defs = tool_defs()
        assert len(defs) == 2


# ──────────────────────────────────────────────────────────────────────────────
# browser tools
# ──────────────────────────────────────────────────────────────────────────────

class TestBrowserTools:
    def test_browser_use_no_playwright(self):
        from ollama_arena.mcp.tools.browser import browser_use
        with mock.patch.dict("sys.modules", {"playwright": None, "playwright.sync_api": None}):
            result = browser_use({"action": "navigate", "url": "http://example.com"})
        assert "Playwright" in result or "Error" in result

    def test_mock_browser_navigate(self):
        from ollama_arena.mcp.tools.browser import mock_browser_navigate
        result = mock_browser_navigate({"url": "http://example.com"})
        data = json.loads(result)
        assert data["status"] == "ok"
        assert data["url"] == "http://example.com"

    def test_mock_browser_navigate_default_url(self):
        from ollama_arena.mcp.tools.browser import mock_browser_navigate
        result = mock_browser_navigate({})
        data = json.loads(result)
        assert data["url"] == "about:blank"

    def test_tool_defs_no_mock(self):
        from ollama_arena.mcp.tools.browser import tool_defs
        defs = tool_defs(include_mock=False)
        assert len(defs) == 1
        assert defs[0][0] == "browser_use"

    def test_tool_defs_with_mock(self):
        from ollama_arena.mcp.tools.browser import tool_defs
        defs = tool_defs(include_mock=True)
        assert len(defs) == 2
        names = [d[0] for d in defs]
        assert "browser_navigate" in names


# ──────────────────────────────────────────────────────────────────────────────
# computer tools
# ──────────────────────────────────────────────────────────────────────────────

class TestComputerTools:
    def test_screenshot_darwin(self):
        from ollama_arena.mcp.tools.computer import computer_screenshot
        with mock.patch("platform.system", return_value="Darwin"):
            with mock.patch("subprocess.run") as m:
                result = computer_screenshot({})
        assert "Screenshot" in result
        m.assert_called_once()

    def test_screenshot_non_darwin(self):
        from ollama_arena.mcp.tools.computer import computer_screenshot
        with mock.patch("platform.system", return_value="Linux"):
            result = computer_screenshot({})
        assert "not supported" in result

    def test_screenshot_exception(self):
        from ollama_arena.mcp.tools.computer import computer_screenshot
        with mock.patch("platform.system", return_value="Darwin"):
            with mock.patch("subprocess.run", side_effect=Exception("screencapture error")):
                result = computer_screenshot({})
        assert "Error" in result

    def test_click_darwin(self):
        from ollama_arena.mcp.tools.computer import computer_click
        with mock.patch("platform.system", return_value="Darwin"):
            with mock.patch("subprocess.run") as m:
                result = computer_click({"x": 100, "y": 200})
        assert "100" in result and "200" in result

    def test_click_non_darwin(self):
        from ollama_arena.mcp.tools.computer import computer_click
        with mock.patch("platform.system", return_value="Linux"):
            result = computer_click({"x": 100, "y": 200})
        assert "not supported" in result

    def test_click_rejects_non_numeric_x_injection(self):
        """x/y were interpolated raw into an osascript -e string with no escaping
        or validation, so a non-numeric x/y let a tool call break out of the
        AppleScript 'click at {x, y}' literal and chain arbitrary commands
        (e.g. 'do shell script'). Numeric coercion must reject this before any
        subprocess call is made."""
        from ollama_arena.mcp.tools.computer import computer_click
        payload = '0}; do shell script "touch /tmp/pwned'
        with mock.patch("platform.system", return_value="Darwin"):
            with mock.patch("subprocess.run") as m:
                result = computer_click({"x": payload, "y": 5})
        assert "Error" in result
        m.assert_not_called()

    def test_click_rejects_non_numeric_y_injection(self):
        from ollama_arena.mcp.tools.computer import computer_click
        with mock.patch("platform.system", return_value="Darwin"):
            with mock.patch("subprocess.run") as m:
                result = computer_click({"x": 5, "y": "1 do shell script \"id\""})
        assert "Error" in result
        m.assert_not_called()

    def test_click_accepts_numeric_string_coordinates(self):
        """Numeric strings (as might arrive from a loosely-typed tool call) are
        still valid — only non-numeric payloads should be rejected."""
        from ollama_arena.mcp.tools.computer import computer_click
        with mock.patch("platform.system", return_value="Darwin"):
            with mock.patch("subprocess.run") as m:
                result = computer_click({"x": "10", "y": "20"})
        assert "10" in result and "20" in result
        m.assert_called_once()

    def test_click_exception(self):
        from ollama_arena.mcp.tools.computer import computer_click
        with mock.patch("platform.system", return_value="Darwin"):
            with mock.patch("subprocess.run", side_effect=Exception("osascript error")):
                result = computer_click({"x": 100, "y": 200})
        assert "Error" in result

    def test_type_darwin(self):
        from ollama_arena.mcp.tools.computer import computer_type
        with mock.patch("platform.system", return_value="Darwin"):
            with mock.patch("subprocess.run") as m:
                result = computer_type({"text": "hello world"})
        assert "hello world" in result

    def test_type_non_darwin(self):
        from ollama_arena.mcp.tools.computer import computer_type
        with mock.patch("platform.system", return_value="Windows"):
            result = computer_type({"text": "hello"})
        assert "not supported" in result

    def test_type_exception(self):
        from ollama_arena.mcp.tools.computer import computer_type
        with mock.patch("platform.system", return_value="Darwin"):
            with mock.patch("subprocess.run", side_effect=Exception("keystroke error")):
                result = computer_type({"text": "test"})
        assert "Error" in result

    def test_tool_defs_count(self):
        from ollama_arena.mcp.tools.computer import tool_defs
        defs = tool_defs()
        assert len(defs) == 3


# ──────────────────────────────────────────────────────────────────────────────
# _eval_node edge cases in data.py
# ──────────────────────────────────────────────────────────────────────────────

class TestEvalNode:
    def test_math_sin(self):
        from ollama_arena.mcp.tools.data import math_solver
        import math
        result = math_solver({"expression": "sin(0)"})
        assert "0" in result

    def test_math_cos(self):
        from ollama_arena.mcp.tools.data import math_solver
        result = math_solver({"expression": "cos(0)"})
        assert "1" in result

    def test_math_log(self):
        from ollama_arena.mcp.tools.data import math_solver
        result = math_solver({"expression": "log(1)"})
        assert "0" in result

    def test_unsupported_unary_operator(self):
        from ollama_arena.mcp.tools.data import math_solver
        result = math_solver({"expression": "~5"})
        assert "Error" in result

    def test_unsupported_function(self):
        from ollama_arena.mcp.tools.data import math_solver
        result = math_solver({"expression": "abs(-5)"})
        assert "Error" in result

    def test_string_constant_rejected(self):
        from ollama_arena.mcp.tools.data import math_solver
        result = math_solver({"expression": "'hello'"})
        assert "Error" in result
