"""Tests for MCP transport layer implementations."""
import asyncio
import pytest
from ollama_arena.mcp.transport import (
    StdioTransport,
    HTTPTransport,
    InMemoryTransport,
    create_transport,
)


class TestInMemoryTransport:
    """Test in-memory transport implementation."""

    def test_basic_execution(self):
        """Test basic tool execution in memory."""
        handlers = {
            "add": lambda args: str(args["a"] + args["b"]),
            "echo": lambda args: args["text"],
        }

        transport = InMemoryTransport(handlers)

        async def test():
            result1 = await transport.send({"name": "add", "arguments": {"a": 2, "b": 3}})
            assert result1["result"] == "5"
            assert result1["error"] is None

            result2 = await transport.send({"name": "echo", "arguments": {"text": "hello"}})
            assert result2["result"] == "hello"

        asyncio.run(test())

    def test_handler_error(self):
        """Test error handling in handlers."""
        handlers = {
            "error": lambda args: 1 / 0,  # Division by zero
        }

        transport = InMemoryTransport(handlers)

        async def test():
            result = await transport.send({"name": "error", "arguments": {}})
            assert result["result"] is None
            assert result["error"] is not None
            assert "division by zero" in result["error"]

        asyncio.run(test())

    def test_unknown_tool(self):
        """Test handling of unknown tools."""
        transport = InMemoryTransport({})

        async def test():
            result = await transport.send({"name": "unknown", "arguments": {}})
            assert result["result"] is None
            assert result["error"] is not None

        asyncio.run(test())

    def test_transport_lifecycle(self):
        """Test transport open/close lifecycle."""
        transport = InMemoryTransport({"test": lambda args: "ok"})

        async def test():
            assert transport.is_alive()
            result = await transport.send({"name": "test", "arguments": {}})
            assert result["result"] == "ok"

            await transport.close()
            assert not transport.is_alive()

        asyncio.run(test())

    def test_closed_transport_error(self):
        """Test that closed transport raises error."""
        transport = InMemoryTransport({"test": lambda args: "ok"})

        async def test():
            await transport.close()
            with pytest.raises(ConnectionError, match="closed"):
                await transport.send({"name": "test", "arguments": {}})

        asyncio.run(test())


class TestTransportFactory:
    """Test transport factory function."""

    def test_create_memory_transport(self):
        """Test creating in-memory transport via factory."""
        handlers = {"test": lambda args: "ok"}
        transport = create_transport("memory", handlers=handlers)

        assert isinstance(transport, InMemoryTransport)
        assert transport.is_alive()

    def test_create_memory_transport_missing_handlers(self):
        """Test that memory transport requires handlers parameter."""
        with pytest.raises(ValueError, match="handlers"):
            create_transport("memory")

    def test_create_http_transport_missing_url(self):
        """Test that HTTP transport requires base_url parameter."""
        with pytest.raises(ValueError, match="base_url"):
            create_transport("http")

    def test_create_stdio_transport_missing_command(self):
        """Test that stdio transport requires command parameter."""
        with pytest.raises(ValueError, match="command"):
            create_transport("stdio")

    def test_create_unknown_transport(self):
        """Test that unknown transport type raises error."""
        with pytest.raises(ValueError, match="Unknown transport type"):
            create_transport("unknown")


class TestHTTPTransport:
    """Test HTTP transport (basic functionality)."""

    def test_init(self):
        """Test HTTP transport initialization."""
        transport = HTTPTransport("http://localhost:8080")
        assert transport.base_url == "http://localhost:8080"
        assert transport.timeout == 30.0

    def test_init_custom_timeout(self):
        """Test HTTP transport with custom timeout."""
        transport = HTTPTransport("http://localhost:8080", timeout=60.0)
        assert transport.timeout == 60.0

    def test_url_normalization(self):
        """Test that URLs are normalized (trailing slashes)."""
        transport1 = HTTPTransport("http://localhost:8080/")
        transport2 = HTTPTransport("http://localhost:8080")
        assert transport1.base_url == transport2.base_url

    def test_is_alive_without_session(self):
        """Test is_alive when session is not created."""
        transport = HTTPTransport("http://localhost:8080")
        assert not transport.is_alive()


class TestStdioTransport:
    """Test stdio transport (basic functionality)."""

    def test_init(self):
        """Test stdio transport initialization."""
        transport = StdioTransport(["echo", "hello"])
        assert transport.command == ["echo", "hello"]
        assert transport.cwd is None

    def test_init_with_cwd(self):
        """Test stdio transport with custom working directory."""
        transport = StdioTransport(["echo", "hello"], cwd="/tmp")
        assert transport.cwd == "/tmp"

    def test_is_alive_without_process(self):
        """Test is_alive when process is not started."""
        transport = StdioTransport(["echo", "hello"])
        assert not transport.is_alive()