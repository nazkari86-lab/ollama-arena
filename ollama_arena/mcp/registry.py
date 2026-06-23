"""Unified MCP tool registry."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Literal

from .tools import browser, code, computer, data, dev, git, network, web, workspace

# RAG tools (optional dependency)
try:
    from ..rag.tools import tool_defs as rag_tool_defs
    _rag_available = True
except ImportError:
    _rag_available = False
    def rag_tool_defs() -> list[tuple[str, Callable, dict, str]]:
        return []

DangerTier = Literal["safe", "confirm", "deny"]


@dataclass
class ToolDef:
    name: str
    handler: Callable[[dict], str]
    schema: dict
    danger_tier: DangerTier = "safe"
    mock_available: bool = True


def _mock_sqlite_query(args: dict) -> str:
    query = args.get("query", "")
    if "users" in query.lower():
        return json.dumps([{"id": 1, "name": "Alice"}])
    return json.dumps([])


def _mock_search_docs(args: dict) -> str:
    query = args.get("query", "")
    return json.dumps(
        {
            "query": query,
            "results": [
                {"title": f"Docs: {query}", "snippet": f"Documentation about {query}."}
            ],
        }
    )


def _collect_builtin_defs(include_mock: bool, server_configs: dict | None) -> list[ToolDef]:
    raw: list[tuple[str, Callable, dict, str]] = []
    raw.extend(web.tool_defs())
    raw.extend(workspace.tool_defs())
    raw.extend(git.tool_defs())
    raw.extend(dev.tool_defs())
    raw.extend(code.tool_defs())
    raw.extend(network.tool_defs())
    raw.extend(data.tool_defs())
    raw.extend(computer.tool_defs())

    # Add RAG tools if available
    if _rag_available:
        raw.extend(rag_tool_defs())

    include_browser_mock = include_mock or bool(server_configs and "playwright" in server_configs)
    raw.extend(browser.tool_defs(include_mock=include_browser_mock))

    defs: list[ToolDef] = [
        ToolDef(name=name, handler=handler, schema=schema, danger_tier=tier)  # type: ignore[arg-type]
        for name, handler, schema, tier in raw
    ]

    include_sqlite_mock = include_mock or bool(server_configs and "sqlite" in server_configs)
    if include_sqlite_mock:
        defs.append(
            ToolDef(
                name="sqlite_query",
                handler=_mock_sqlite_query,
                schema={
                    "type": "function",
                    "function": {
                        "name": "sqlite_query",
                        "description": "Query the benchmark SQLite database (mock).",
                        "parameters": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                            "required": ["query"],
                        },
                    },
                },
                danger_tier="confirm",
                mock_available=True,
            )
        )

    if include_mock:
        defs.append(
            ToolDef(
                name="search_docs",
                handler=_mock_search_docs,
                schema={
                    "type": "function",
                    "function": {
                        "name": "search_docs",
                        "description": "Search documentation (mock Context7-style).",
                        "parameters": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                            "required": ["query"],
                        },
                    },
                },
                danger_tier="safe",
                mock_available=True,
            )
        )

    return defs


def build_tool_registry(
    *,
    use_mock: bool = False,
    server_configs: dict | None = None,
) -> dict[str, ToolDef]:
    """Build the name -> ToolDef map for the orchestrator."""
    registry: dict[str, ToolDef] = {}
    for tool in _collect_builtin_defs(include_mock=use_mock, server_configs=server_configs):
        registry[tool.name] = tool
    return registry
