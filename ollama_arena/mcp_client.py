"""Backward-compatible re-export of the MCP orchestrator and legacy symbols."""
from .mcp.orchestrator import MCPOrchestrator
from .mcp.tools.workspace import SecurityError, WORKSPACE_DIR, _safe_path
from .mcp.tools.web import ddg_search as _real_ddg_search
from .mcp.tools.web import wikipedia_search as _real_wikipedia_search
from .sandboxes.runner import run_in_language

__all__ = [
    "MCPOrchestrator",
    "SecurityError",
    "WORKSPACE_DIR",
    "_safe_path",
    "_real_ddg_search",
    "_real_wikipedia_search",
    "run_in_language",
]
