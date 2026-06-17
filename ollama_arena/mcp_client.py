"""MCP tool orchestration for agentic tool-use benchmarks."""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger("arena.mcp")

# In-memory demo DB for sqlite_query when no real MCP server is connected.
_DEMO_DB_PATH: Optional[Path] = None


def _demo_db() -> Path:
    global _DEMO_DB_PATH
    if _DEMO_DB_PATH is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        _DEMO_DB_PATH = Path(tmp.name)
        cx = sqlite3.connect(_DEMO_DB_PATH)
        cx.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)"
        )
        cx.executemany(
            "INSERT INTO users (name, email) VALUES (?, ?)",
            [
                ("Alice", "alice@example.com"),
                ("Bob", "bob@example.com"),
                ("Carol", "carol@example.com"),
            ],
        )
        cx.commit()
        cx.close()
    return _DEMO_DB_PATH


def _mock_sqlite_query(args: dict) -> str:
    query = (args.get("query") or "").strip()
    if not query.upper().startswith("SELECT"):
        return "Error: only SELECT queries are allowed in the demo database."
    try:
        cx = sqlite3.connect(_demo_db())
        rows = cx.execute(query).fetchall()
        cx.close()
        return json.dumps(
            [{"id": r[0], "name": r[1], "email": r[2]} for r in rows]
        )
    except sqlite3.Error as exc:
        return f"SQLite error: {exc}"


def _mock_browser_navigate(args: dict) -> str:
    url = args.get("url", "")
    return (
        f"Page title: Example Domain\nURL: {url}\n"
        "Body: Welcome to the mock browser. Latest AI news headlines appear here."
    )


def _mock_search_docs(args: dict) -> str:
    query = args.get("query") or args.get("q") or "docker"
    return (
        f"Documentation results for '{query}':\n"
        "1. Docker overview — container runtime and image workflow\n"
        "2. Docker Compose — multi-service orchestration\n"
    )


def _mock_git_commit(args: dict) -> str:
    message = args.get("message") or args.get("msg") or "(no message)"
    return f"Committed successfully with message: {message}"


_MOCK_HANDLERS: dict[str, Callable[[dict], str]] = {
    "sqlite_query": _mock_sqlite_query,
    "browser_navigate": _mock_browser_navigate,
    "search_docs": _mock_search_docs,
    "git_commit": _mock_git_commit,
}

_TOOL_SCHEMAS: dict[str, dict] = {
    "sqlite_query": {
        "type": "function",
        "function": {
            "name": "sqlite_query",
            "description": "Execute a SELECT query on the SQLite database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The SQL query to run."}
                },
                "required": ["query"],
            },
        },
    },
    "browser_navigate": {
        "type": "function",
        "function": {
            "name": "browser_navigate",
            "description": "Navigate to a URL using a headless browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to visit."}
                },
                "required": ["url"],
            },
        },
    },
    "search_docs": {
        "type": "function",
        "function": {
            "name": "search_docs",
            "description": "Search technical documentation (Context7-style).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."}
                },
                "required": ["query"],
            },
        },
    },
    "git_commit": {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": "Create a git commit with the given message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Commit message."}
                },
                "required": ["message"],
            },
        },
    },
}

# Map stack config keys → tool names exposed when that stack is enabled.
_STACK_TOOLS: dict[str, list[str]] = {
    "sqlite": ["sqlite_query"],
    "playwright": ["browser_navigate"],
    "searxng": ["search_docs"],
    "git": ["git_commit"],
    "context7": ["search_docs"],
}


class MCPOrchestrator:
    """Manages tool definitions and execution for Tool-Use benchmarking."""

    def __init__(
        self,
        server_configs: Optional[Dict[str, Dict[str, Any]]] = None,
        *,
        use_mock: Optional[bool] = None,
        config_path: Optional[str] = None,
    ):
        # If no server_configs given, try loading from MCPConfig file
        if server_configs is None:
            try:
                from .mcp_config import load_mcp_config
                file_cfg = load_mcp_config(config_path)
                server_configs = {
                    name: {"command": srv.command, "args": srv.args, "env": srv.env}
                    for name, srv in file_cfg.servers.items()
                }
            except Exception:
                server_configs = {}
        self.configs = server_configs or {}
        self.use_mock = (
            use_mock
            if use_mock is not None
            else os.environ.get("ARENA_MCP_MOCK", "1") != "0"
        )
        self.active_tools: List[Dict[str, Any]] = []
        self._handlers: dict[str, Callable[[dict], str]] = dict(_MOCK_HANDLERS)
        self._load_tools_from_config()

    def _load_tools_from_config(self) -> None:
        self.active_tools = []
        if not self.configs:
            # Default benchmark stack: all mock tools available.
            for schema in _TOOL_SCHEMAS.values():
                self.active_tools.append(schema)
            return

        seen: set[str] = set()
        for stack_key in self.configs:
            for tool_name in _STACK_TOOLS.get(stack_key, []):
                if tool_name in seen:
                    continue
                schema = _TOOL_SCHEMAS.get(tool_name)
                if schema:
                    self.active_tools.append(schema)
                    seen.add(tool_name)

    async def get_all_tools(self) -> List[Dict[str, Any]]:
        return list(self.active_tools)

    async def execute_tool(self, name: str, arguments: dict) -> str:
        log.info("[mcp] executing tool: %s args=%s mock=%s", name, arguments, self.use_mock)
        handler = self._handlers.get(name)
        if handler is None:
            return f"Error: Tool {name} not found."
        if self.use_mock:
            return handler(arguments or {})
        # Real MCP path: extend here with stdio ClientSession when ARENA_MCP_MOCK=0.
        try:
            return await self._execute_real_mcp(name, arguments or {})
        except Exception as exc:
            log.warning("[mcp] real MCP failed for %s, falling back to mock: %s", name, exc)
            return handler(arguments or {})

    async def _execute_real_mcp(self, name: str, arguments: dict) -> str:
        """Optional real MCP via the official Python SDK (extra dep: mcp)."""
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError as exc:
            raise RuntimeError(
                "Install optional MCP support: pip install 'ollama-arena[mcp]'"
            ) from exc

        stack_key = self._stack_for_tool(name)
        cfg = self.configs.get(stack_key) if stack_key else None
        if not cfg or "command" not in cfg:
            raise RuntimeError(f"No stdio MCP config for tool {name}")

        params = StdioServerParameters(
            command=cfg["command"],
            args=cfg.get("args", []),
            env=cfg.get("env"),
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments)
                parts = []
                for block in result.content:
                    text = getattr(block, "text", None)
                    if text:
                        parts.append(text)
                return "\n".join(parts) if parts else str(result)

    def _stack_for_tool(self, name: str) -> Optional[str]:
        for stack, names in _STACK_TOOLS.items():
            if name in names:
                return stack
        return None

    def register_handler(self, name: str, handler: Callable[[dict], str]) -> None:
        """Test hook: override or add a tool handler."""
        self._handlers[name] = handler
