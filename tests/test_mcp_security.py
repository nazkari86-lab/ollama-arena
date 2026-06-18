"""MCP security gate and workspace path containment."""
import os
import pytest
from unittest.mock import patch

from ollama_arena.mcp_client import MCPOrchestrator, SecurityError, _safe_path, WORKSPACE_DIR


@pytest.fixture
def orch():
    return MCPOrchestrator()


def test_safe_path_rejects_traversal():
    with pytest.raises(SecurityError):
        _safe_path("../../etc/passwd")


def test_safe_path_resolves_under_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr("ollama_arena.mcp.tools.workspace.WORKSPACE_DIR", tmp_path)
    p = _safe_path("notes.txt")
    assert str(p).startswith(str(tmp_path.resolve()))


@pytest.mark.asyncio
async def test_dangerous_tool_denied_non_tty(orch, monkeypatch):
    monkeypatch.delenv("ARENA_AUTO_APPROVE", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    with patch("sys.stdin.isatty", return_value=False):
        out = await orch.execute_tool("write_file", {"path": "x.txt", "content": "hi"})
    assert "denied" in out.lower()


@pytest.mark.asyncio
async def test_dangerous_tool_allowed_with_auto_approve(orch, monkeypatch, tmp_path):
    monkeypatch.setenv("ARENA_AUTO_APPROVE", "1")
    monkeypatch.setattr("ollama_arena.mcp.tools.workspace.WORKSPACE_DIR", tmp_path)
    out = await orch.execute_tool("write_file", {"path": "ok.txt", "content": "data"})
    assert "Wrote" in out
    assert (tmp_path / "ok.txt").read_text() == "data"


@pytest.mark.asyncio
async def test_read_file_path_escape(orch, monkeypatch):
    monkeypatch.setenv("ARENA_AUTO_APPROVE", "1")
    out = await orch.execute_tool("read_file", {"path": "../../../etc/passwd"})
    assert "escape" in out.lower() or "Error" in out


@pytest.mark.asyncio
async def test_code_interpreter_uses_docker(monkeypatch, orch):
    monkeypatch.setenv("ARENA_AUTO_APPROVE", "1")
    called = {}

    def fake_run(code, **kw):
        called["use_docker"] = kw.get("use_docker")
        from ollama_arena.sandboxes.base import RunResult
        return RunResult(output="42", accepted=True, language="python")

    with patch("ollama_arena.mcp.tools.code.run_in_language", side_effect=fake_run):
        await orch.execute_tool("code_interpreter", {"code": "print(42)"})
    assert called.get("use_docker") is True
