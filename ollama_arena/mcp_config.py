"""MCP server configuration management."""
from __future__ import annotations
import json, logging
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("arena.mcp_config")

DEFAULT_CONFIG: dict = {
    "servers": {
        "sqlite": {
            "command": "uvx",
            "args": ["mcp-server-sqlite", "--db-path", str(Path.home() / "arena_mcp.db")],
            "description": "SQLite database access for agentic tasks",
        },
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem",
                     str(Path.home() / "arena_workspace")],
            "description": "Safe filesystem access in workspace dir",
        },
    }
}

_CONFIG_PATH = Path.home() / ".config" / "ollama-arena" / "mcp_servers.json"


@dataclass
class ServerConfig:
    command: str
    args: list[str] = field(default_factory=list)
    description: str = ""
    env: dict = field(default_factory=dict)


@dataclass
class MCPConfig:
    servers: dict[str, ServerConfig] = field(default_factory=dict)


def load_mcp_config(path: str | None = None) -> MCPConfig:
    p = Path(path) if path else _CONFIG_PATH
    raw: dict = {}
    if p.exists():
        try:
            raw = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError) as e:
            log.warning(f"MCP config load error ({p}): {e}. Using defaults.")
            raw = DEFAULT_CONFIG
    else:
        raw = DEFAULT_CONFIG

    servers = {}
    for name, cfg in raw.get("servers", {}).items():
        servers[name] = ServerConfig(
            command=cfg.get("command", ""),
            args=cfg.get("args", []),
            description=cfg.get("description", ""),
            env=cfg.get("env", {}),
        )
    return MCPConfig(servers=servers)


def save_default_config() -> Path:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2))
    return _CONFIG_PATH
