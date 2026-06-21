"""Additional tests for mcp/transport.py — missing lines coverage."""
from __future__ import annotations

import asyncio
import json
import unittest.mock as mock
import pytest


# ──────────────────────────────────────────────────────────────────────────────
# StdioTransport — is_alive / close
# ──────────────────────────────────────────────────────────────────────────────

class TestStdioTransportIsAlive:
    def test_not_alive_when_no_process(self):
        from ollama_arena.mcp.transport import StdioTransport
        t = StdioTransport(["echo", "hello"])
        assert t.is_alive() is False

    def test_alive_when_process_running(self):
        from ollama_arena.mcp.transport import StdioTransport
        t = StdioTransport(["echo", "hello"])
        mock_proc = mock.MagicMock()
        mock_proc.poll.return_value = None  # still running
        t.process = mock_proc
        assert t.is_alive() is True

    def test_not_alive_when_process_exited(self):
        from ollama_arena.mcp.transport import StdioTransport
        t = StdioTransport(["echo", "hello"])
        mock_proc = mock.MagicMock()
        mock_proc.poll.return_value = 0  # exited
        t.process = mock_proc
        assert t.is_alive() is False


class TestStdioTransportClose:
    @pytest.mark.asyncio
    async def test_close_terminates_process(self):
        from ollama_arena.mcp.transport import StdioTransport
        t = StdioTransport(["echo"])
        mock_proc = mock.MagicMock()
        mock_writer = mock.MagicMock()
        mock_writer.close = mock.MagicMock()
        t.process = mock_proc
        t._writer = mock_writer
        t._reader = mock.MagicMock()
        await t.close()
        mock_proc.terminate.assert_called_once()
        assert t.process is None
        assert t._writer is None
        assert t._reader is None

    @pytest.mark.asyncio
    async def test_close_kills_on_timeout(self):
        from ollama_arena.mcp.transport import StdioTransport
        import subprocess
        t = StdioTransport(["echo"])
        mock_proc = mock.MagicMock()
        # Make terminate succeed but wait() raise TimeoutExpired
        mock_proc.terminate = mock.MagicMock()
        mock_proc.wait = mock.MagicMock(side_effect=[subprocess.TimeoutExpired(["cmd"], 5), None])
        mock_proc.kill = mock.MagicMock()
        t.process = mock_proc
        await t.close()
        mock_proc.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_no_process_noop(self):
        from ollama_arena.mcp.transport import StdioTransport
        t = StdioTransport(["echo"])
        # Should not raise when no process
        await t.close()
        assert t.process is None


# ──────────────────────────────────────────────────────────────────────────────
# HTTPTransport — init, is_alive, close, _get_session
# ──────────────────────────────────────────────────────────────────────────────

class TestHTTPTransport:
    def test_init_url_stripped(self):
        from ollama_arena.mcp.transport import HTTPTransport
        t = HTTPTransport("http://localhost:8080/")
        assert t.base_url == "http://localhost:8080"

    def test_not_alive_when_no_session(self):
        from ollama_arena.mcp.transport import HTTPTransport
        t = HTTPTransport("http://localhost:8080")
        assert t.is_alive() is False

    def test_alive_when_session_open(self):
        from ollama_arena.mcp.transport import HTTPTransport
        t = HTTPTransport("http://localhost:8080")
        mock_session = mock.MagicMock()
        mock_session.closed = False
        t._session = mock_session
        assert t.is_alive() is True

    def test_not_alive_when_session_closed(self):
        from ollama_arena.mcp.transport import HTTPTransport
        t = HTTPTransport("http://localhost:8080")
        mock_session = mock.MagicMock()
        mock_session.closed = True
        t._session = mock_session
        assert t.is_alive() is False

    @pytest.mark.asyncio
    async def test_close_closes_session(self):
        from ollama_arena.mcp.transport import HTTPTransport
        t = HTTPTransport("http://localhost:8080")
        mock_session = mock.AsyncMock()
        t._session = mock_session
        await t.close()
        mock_session.close.assert_called_once()
        assert t._session is None

    @pytest.mark.asyncio
    async def test_close_no_session_noop(self):
        from ollama_arena.mcp.transport import HTTPTransport
        t = HTTPTransport("http://localhost:8080")
        await t.close()  # Should not raise

    @pytest.mark.asyncio
    async def test_get_session_no_aiohttp_raises(self):
        from ollama_arena.mcp.transport import HTTPTransport
        t = HTTPTransport("http://localhost:8080")
        with mock.patch.dict("sys.modules", {"aiohttp": None}):
            with pytest.raises((ImportError, Exception)):
                await t._get_session()

    @pytest.mark.asyncio
    async def test_get_session_cached(self):
        from ollama_arena.mcp.transport import HTTPTransport
        t = HTTPTransport("http://localhost:8080")
        mock_session = mock.MagicMock()
        t._session = mock_session
        result = await t._get_session()
        assert result is mock_session


# ──────────────────────────────────────────────────────────────────────────────
# InMemoryTransport — send coverage
# ──────────────────────────────────────────────────────────────────────────────

class TestInMemoryTransportSend:
    @pytest.mark.asyncio
    async def test_send_when_closed_raises(self):
        from ollama_arena.mcp.transport import InMemoryTransport
        t = InMemoryTransport({"tool": lambda args: "result"})
        await t.close()
        with pytest.raises(ConnectionError):
            await t.send({"name": "tool"})

    @pytest.mark.asyncio
    async def test_send_missing_name_returns_error(self):
        from ollama_arena.mcp.transport import InMemoryTransport
        t = InMemoryTransport({})
        result = await t.send({"arguments": {}})
        assert result["error"] is not None
        assert "name" in result["error"]

    @pytest.mark.asyncio
    async def test_send_unknown_tool_returns_error(self):
        from ollama_arena.mcp.transport import InMemoryTransport
        t = InMemoryTransport({})
        result = await t.send({"name": "nonexistent_tool"})
        assert result["error"] is not None
        assert "Unknown tool" in result["error"]

    @pytest.mark.asyncio
    async def test_send_sync_handler(self):
        from ollama_arena.mcp.transport import InMemoryTransport
        t = InMemoryTransport({"add": lambda args: args.get("a", 0) + args.get("b", 0)})
        result = await t.send({"name": "add", "arguments": {"a": 3, "b": 4}})
        assert result["result"] == 7
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_send_async_handler(self):
        from ollama_arena.mcp.transport import InMemoryTransport
        async def async_handler(args):
            return "async_result"
        t = InMemoryTransport({"async_tool": async_handler})
        result = await t.send({"name": "async_tool"})
        assert result["result"] == "async_result"

    @pytest.mark.asyncio
    async def test_send_handler_raises_returns_error(self):
        from ollama_arena.mcp.transport import InMemoryTransport
        def fail_handler(args):
            raise ValueError("something went wrong")
        t = InMemoryTransport({"fail": fail_handler})
        result = await t.send({"name": "fail"})
        assert result["result"] is None
        assert "something went wrong" in result["error"]


# ──────────────────────────────────────────────────────────────────────────────
# create_transport factory
# ──────────────────────────────────────────────────────────────────────────────

class TestCreateTransport:
    def test_stdio_requires_command(self):
        from ollama_arena.mcp.transport import create_transport
        with pytest.raises(ValueError, match="command"):
            create_transport("stdio")

    def test_stdio_creates_stdio_transport(self):
        from ollama_arena.mcp.transport import create_transport, StdioTransport
        t = create_transport("stdio", command=["echo", "hello"])
        assert isinstance(t, StdioTransport)

    def test_stdio_with_cwd(self):
        from ollama_arena.mcp.transport import create_transport, StdioTransport
        t = create_transport("stdio", command=["ls"], cwd="/tmp")
        assert isinstance(t, StdioTransport)
        assert t.cwd == "/tmp"

    def test_http_requires_base_url(self):
        from ollama_arena.mcp.transport import create_transport
        with pytest.raises(ValueError, match="base_url"):
            create_transport("http")

    def test_http_creates_http_transport(self):
        from ollama_arena.mcp.transport import create_transport, HTTPTransport
        t = create_transport("http", base_url="http://localhost:8080")
        assert isinstance(t, HTTPTransport)

    def test_http_with_custom_timeout(self):
        from ollama_arena.mcp.transport import create_transport, HTTPTransport
        t = create_transport("http", base_url="http://localhost:8080", timeout=60.0)
        assert isinstance(t, HTTPTransport)
        assert t.timeout == 60.0

    def test_memory_requires_handlers(self):
        from ollama_arena.mcp.transport import create_transport
        with pytest.raises(ValueError, match="handlers"):
            create_transport("memory")

    def test_memory_creates_in_memory_transport(self):
        from ollama_arena.mcp.transport import create_transport, InMemoryTransport
        t = create_transport("memory", handlers={"echo": lambda a: a})
        assert isinstance(t, InMemoryTransport)

    def test_unknown_type_raises(self):
        from ollama_arena.mcp.transport import create_transport
        with pytest.raises(ValueError, match="Unknown transport"):
            create_transport("websocket")

    def test_case_insensitive(self):
        from ollama_arena.mcp.transport import create_transport, StdioTransport
        t = create_transport("STDIO", command=["echo"])
        assert isinstance(t, StdioTransport)
