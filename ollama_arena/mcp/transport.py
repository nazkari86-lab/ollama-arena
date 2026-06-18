"""MCP transport layer abstraction for different communication methods."""
from __future__ import annotations

import asyncio
import json
import subprocess
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class MCPTransport(ABC):
    """Abstract base class for MCP transport implementations."""

    @abstractmethod
    async def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send a message and receive a response."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the transport connection."""
        pass

    @abstractmethod
    def is_alive(self) -> bool:
        """Check if the transport connection is alive."""
        pass


class StdioTransport(MCPTransport):
    """Transport implementation using stdio (standard input/output)."""

    def __init__(self, command: list[str], cwd: Optional[str] = None):
        self.command = command
        self.cwd = cwd
        self.process: Optional[subprocess.Popen] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None

    async def _start_process(self) -> None:
        """Start the subprocess for stdio communication."""
        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.cwd,
            text=False,
        )

        # Create asyncio streams for non-blocking I/O
        loop = asyncio.get_event_loop()
        self._reader = asyncio.StreamReader()
        reader_protocol = asyncio.StreamReaderProtocol(self._reader)
        await loop.connect_read_pipe(lambda: reader_protocol, self.process.stdout)

        self._writer, _ = await loop.connect_write_pipe(
            lambda: asyncio.StreamReaderProtocol(asyncio.StreamReader()),
            self.process.stdin
        )

    async def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send a message via stdio and receive response."""
        if self.process is None:
            await self._start_process()

        message_str = json.dumps(message) + "\n"
        self._writer.write(message_str.encode())
        await self._writer.drain()

        # Read response
        response_line = await self._reader.readline()
        if not response_line:
            raise ConnectionError("No response from MCP server")

        try:
            return json.loads(response_line.decode())
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response: {e}")

    async def close(self) -> None:
        """Close the subprocess and clean up resources."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()

            self.process = None

        if self._writer:
            self._writer.close()
            self._writer = None

        self._reader = None

    def is_alive(self) -> bool:
        """Check if the subprocess is still running."""
        return self.process is not None and self.process.poll() is None


class HTTPTransport(MCPTransport):
    """Transport implementation using HTTP (for HTTP-based MCP servers)."""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._session: Optional[Any] = None  # aiohttp session

    async def _get_session(self) -> Any:
        """Lazy load aiohttp session."""
        if self._session is None:
            try:
                import aiohttp
                self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
            except ImportError:
                raise ImportError("aiohttp is required for HTTP transport. Install with: pip install aiohttp")
        return self._session

    async def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send a message via HTTP POST."""
        session = await self._get_session()
        url = f"{self.base_url}/rpc"

        async with session.post(url, json=message) as response:
            if response.status != 200:
                raise ConnectionError(f"HTTP error {response.status}: {await response.text()}")
            return await response.json()

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None

    def is_alive(self) -> bool:
        """Check if HTTP session is active."""
        return self._session is not None and not self._session.closed


class InMemoryTransport(MCPTransport):
    """Transport implementation for in-memory tool execution (no external server)."""

    def __init__(self, handlers: Dict[str, Any]):
        self.handlers = handlers
        self._closed = False

    async def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tool call in memory."""
        if self._closed:
            raise ConnectionError("Transport is closed")

        tool_name = message.get("name")
        if not tool_name:
            return {
                "result": None,
                "error": "Message missing 'name' field",
            }

        handler = self.handlers.get(tool_name)
        if not handler:
            return {
                "result": None,
                "error": f"Unknown tool: {tool_name}",
            }

        try:
            # Execute the handler (it might be sync or async)
            result = handler(message.get("arguments", {}))
            if asyncio.iscoroutine(result):
                result = await result

            return {
                "result": result,
                "error": None,
            }
        except Exception as e:
            return {
                "result": None,
                "error": str(e),
            }

    async def close(self) -> None:
        """Mark transport as closed."""
        self._closed = True

    def is_alive(self) -> bool:
        """Check if transport is still usable."""
        return not self._closed


def create_transport(transport_type: str, **kwargs: Any) -> MCPTransport:
    """Factory function to create transport instances."""
    transport_type = transport_type.lower()

    if transport_type == "stdio":
        command = kwargs.get("command")
        if not command:
            raise ValueError("stdio transport requires 'command' parameter")
        return StdioTransport(command, cwd=kwargs.get("cwd"))

    elif transport_type == "http":
        base_url = kwargs.get("base_url")
        if not base_url:
            raise ValueError("HTTP transport requires 'base_url' parameter")
        return HTTPTransport(base_url, timeout=kwargs.get("timeout", 30.0))

    elif transport_type == "memory":
        handlers = kwargs.get("handlers")
        if not handlers:
            raise ValueError("In-memory transport requires 'handlers' parameter")
        return InMemoryTransport(handlers)

    else:
        raise ValueError(f"Unknown transport type: {transport_type}")