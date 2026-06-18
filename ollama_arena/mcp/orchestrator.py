"""MCP orchestrator — dispatches tool calls through the unified registry."""
from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, List, Optional

from .registry import ToolDef, build_tool_registry
from .security import check_security_gate

log = logging.getLogger("arena.mcp")


class MCPOrchestrator:
    def __init__(
        self,
        server_configs: Optional[dict] = None,
        use_mock: Optional[bool] = None,
    ):
        self.server_configs = server_configs or {}
        if use_mock is None:
            if os.environ.get("ARENA_MCP_MOCK") == "0":
                use_mock = False
            else:
                use_mock = bool(self.server_configs)
        self._use_mock = use_mock
        self._reload_registry()

    @property
    def use_mock(self) -> bool:
        return self._use_mock

    @use_mock.setter
    def use_mock(self, value: bool) -> None:
        self._use_mock = value
        self._reload_registry()

    def _reload_registry(self) -> None:
        self._registry: dict[str, ToolDef] = build_tool_registry(
            use_mock=self._use_mock,
            server_configs=self.server_configs,
        )
        self._handlers: dict[str, Callable[[dict], str]] = {
            name: tool.handler for name, tool in self._registry.items()
        }
        self.active_tools: List[Dict[str, Any]] = [
            tool.schema for tool in self._registry.values()
        ]

    async def get_all_tools(self) -> List[Dict[str, Any]]:
        return list(self.active_tools)

    async def execute_tool(self, name: str, arguments: dict) -> str:
        log.info("[mcp] %s(%s)", name, arguments)
        tool = self._registry.get(name)
        if not tool:
            return f"Error: {name} not found."

        allowed, msg = check_security_gate(name, arguments or {}, tool.danger_tier)
        if not allowed:
            return msg

        try:
            return tool.handler(arguments or {})
        except Exception as exc:
            log.exception("[mcp] tool %s failed", name)
            return f"Execution error: {exc}"

    def register_handler(self, name: str, handler: Callable[[dict], str]) -> None:
        self._handlers[name] = handler
        if name in self._registry:
            self._registry[name].handler = handler
