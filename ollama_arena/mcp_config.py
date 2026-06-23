"""MCP server configuration management."""
from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("arena.mcp_config")

DEFAULT_CONFIG: dict = {
    "servers": {
        # Database servers
        "sqlite": {
            "command": "uvx",
            "args": ["mcp-server-sqlite", "--db-path", str(Path.home() / "arena_mcp.db")],
            "description": "SQLite database access for agentic tasks",
            "tier": "essential",
        },

        # Filesystem access
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem",
                     str(Path.home() / "arena_workspace")],
            "description": "Safe filesystem access in workspace dir",
            "tier": "essential",
        },

        # Memory and context
        "memory": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-memory"],
            "description": "Persistent memory storage for agent context",
            "tier": "essential",
        },

        # Web search and browsing
        "brave-search": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-brave-search"],
            "description": "Brave web search (free tier, no API key required)",
            "tier": "useful",
            "env": {"BRAVE_API_KEY": ""},  # Optional - works with free tier
        },

        "puppeteer": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-puppeteer"],
            "description": "Browser automation with Puppeteer",
            "tier": "advanced",
        },

        # Development tools
        "git": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-git", "--repository", str(Path.cwd())],
            "description": "Git repository operations and history",
            "tier": "useful",
        },

        "github": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "description": "GitHub API access (free tier available)",
            "tier": "useful",
            "env": {"GITHUB_TOKEN": ""},  # Optional - works without token for public repos
        },

        # System integration
        "postgres": {
            "command": "uvx",
            "args": ["mcp-server-postgres", "--connection-string", "postgresql://localhost:5432/arena"],
            "description": "PostgreSQL database access (requires local Postgres)",
            "tier": "advanced",
        },

        # Content and media
        "youtube-transcript": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-youtube-transcript"],
            "description": "YouTube video transcript extraction",
            "tier": "useful",
        },

        "sequential-thinking": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
            "description": "Sequential thinking reasoning enhancement",
            "tier": "advanced",
        },

        # Data processing
        "everything": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-everything"],
            "description": "Everything search integration (local file search)",
            "tier": "useful",
        },

        # AI/LLM integration
        "openai": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-openai"],
            "description": "OpenAI API access (requires API key)",
            "tier": "advanced",
            "env": {"OPENAI_API_KEY": ""},  # User must provide
        },

        # Time and utilities
        "time": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-time"],
            "description": "Current time and date information",
            "tier": "essential",
        },

        # Devin Marketplace servers (unique/external MCP servers)
        "context7": {
            "command": "npx",
            "args": ["-y", "@context7/mcp-server"],
            "description": "Up-to-date code docs for any prompt (Devin marketplace)",
            "tier": "useful",
            "enabled": True,
            "requires_api_key": False,
            "is_external": True,
        },

        "fetch": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-fetch"],
            "description": "Web content fetching and conversion (Devin marketplace)",
            "tier": "useful",
            "enabled": False,  # Currently disabled due to error in Devin marketplace
            "requires_api_key": False,
            "is_external": True,
        },

        "tavily": {
            "command": "npx",
            "args": ["-y", "@tavily/mcp-server"],
            "description": "Tavily search integration from Devin marketplace",
            "tier": "useful",
            "enabled": True,
            "requires_api_key": True,  # Tavily requires API key
            "is_external": True,
        },

        "playwright": {
            "command": "npx",
            "args": ["-y", "@executeautomation/playwright-mcp-server"],
            "description": "Playwright browser automation from Devin marketplace",
            "tier": "advanced",
            "enabled": True,
            "requires_api_key": False,
            "is_external": True,
        },

        "mcp_docker": {
            "command": "npx",
            "args": ["-y", "@docker/mcp-server"],
            "description": "Docker integration from Devin marketplace",
            "tier": "advanced",
            "enabled": True,
            "requires_api_key": False,
            "is_external": True,
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
    tier: str = "useful"  # essential, useful, advanced
    enabled: bool = True
    requires_api_key: bool = False
    is_external: bool = False  # For Devin Marketplace servers
    url: str = ""  # For URL-based external servers
    transport: str = "stdio"  # stdio, http, or memory


@dataclass
class MCPConfig:
    servers: dict[str, ServerConfig] = field(default_factory=dict)

    def get_enabled_servers(self, tier: str | None = None) -> dict[str, ServerConfig]:
        """Get enabled servers, optionally filtered by tier."""
        servers = {}
        for name, config in self.servers.items():
            if not config.enabled:
                continue
            if tier and config.tier != tier:
                continue
            servers[name] = config
        return servers

    def get_servers_by_tier(self, tier: str) -> dict[str, ServerConfig]:
        """Get all servers of a specific tier."""
        return {
            name: config
            for name, config in self.servers.items()
            if config.tier == tier
        }


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
        # Check if server is explicitly disabled
        if not cfg.get("enabled", True):
            log.info(f"MCP server '{name}' is disabled in config")
            continue

        servers[name] = ServerConfig(
            command=cfg.get("command", ""),
            args=cfg.get("args", []),
            description=cfg.get("description", ""),
            env=cfg.get("env", {}),
            tier=cfg.get("tier", "useful"),
            enabled=cfg.get("enabled", True),
            requires_api_key=cfg.get("requires_api_key", False),
            is_external=cfg.get("is_external", False),
            url=cfg.get("url", ""),
            transport=cfg.get("transport", "stdio"),
        )
    return MCPConfig(servers=servers)


def save_default_config() -> Path:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2))
    return _CONFIG_PATH


def check_server_availability(config: ServerConfig) -> tuple[bool, str]:
    """Check if a server command is available and can be executed.
    Returns (is_available, reason)."""
    import shutil
    import subprocess

    # For external servers (URL-based), we can't easily check availability
    if config.is_external and config.url:
        return True, f"External server (URL: {config.url})"

    command = config.command
    try:
        # Check if command exists
        if not shutil.which(command):
            return False, f"Command '{command}' not found in PATH"

        # Try to get version/help to verify it works
        test_args = config.args[:1] if config.args else ["--help"]
        result = subprocess.run(
            [command] + test_args,
            capture_output=True,
            text=True,
            timeout=10,
        )

        # If command doesn't fail catastrophically, consider it available
        if result.returncode in [0, 1, 2]:  # 0=success, 1/2=common for --help failures
            return True, f"Server '{command}' is available"
        else:
            return False, f"Server '{command}' failed with code {result.returncode}"

    except subprocess.TimeoutExpired:
        return False, f"Server '{command}' timed out during availability check"
    except FileNotFoundError:
        return False, f"Command '{command}' not found"
    except Exception as e:
        return False, f"Error checking server '{command}': {str(e)}"


def detect_common_issues(config: ServerConfig) -> list[str]:
    """Detect common configuration issues with MCP servers."""
    issues = []

    # Check if Node.js/npm/npx is required but not available
    if config.command in ["npx", "npm"]:
        import shutil
        if not shutil.which("node"):
            issues.append("Node.js is not installed")
        if not shutil.which("npx"):
            issues.append("npx is not installed")

    # Check if uvx is required but not available
    if config.command in ["uvx", "uv"]:
        import shutil
        if not shutil.which("uv"):
            issues.append("uv (Python package installer) is not installed")

    # Check for required environment variables
    for env_var, default_value in config.env.items():
        if not default_value and not config.env.get(env_var):
            import os
            if not os.environ.get(env_var):
                issues.append(f"Environment variable {env_var} is not set")

    # Check for required workspace directories
    if "arena_workspace" in str(config.args):
        workspace = Path.home() / "arena_workspace"
        if not workspace.exists():
            issues.append(f"Workspace directory {workspace} does not exist")

    return issues


def diagnose_mcp_servers(config: MCPConfig) -> dict[str, dict]:
    """Diagnose all MCP servers and return status information."""
    results = {}

    for name, server_config in config.servers.items():
        is_available, reason = check_server_availability(server_config)
        common_issues = detect_common_issues(server_config)

        # Check if required environment variables are set
        missing_env = []
        for env_var, default_value in server_config.env.items():
            import os
            if not default_value and not os.environ.get(env_var):
                if server_config.requires_api_key:
                    missing_env.append(env_var)

        results[name] = {
            "available": is_available,
            "reason": reason,
            "common_issues": common_issues,
            "missing_env": missing_env,
            "tier": server_config.tier,
            "enabled": server_config.enabled,
            "requires_api_key": server_config.requires_api_key,
            "is_external": server_config.is_external,
            "transport": server_config.transport,
        }

    return results


def print_server_diagnostics(diag_results: dict[str, dict]) -> None:
    """Print formatted server diagnostics."""
    print("\n🔍 MCP Server Diagnostics:")
    print("=" * 80)

    essential_count = 0
    useful_count = 0
    advanced_count = 0
    available_count = 0
    external_count = 0

    for name, result in diag_results.items():
        status = "✅" if result["available"] else "❌"
        tier_icon = {"essential": "🔥", "useful": "⚡", "advanced": "🚀"}[result["tier"]]
        external_icon = "🌐" if result["is_external"] else ""

        print(f"{status} {tier_icon} {external_icon} {name:30} [{result['tier']}]")

        if result["available"]:
            available_count += 1
        else:
            print(f"   ⚠️  {result['reason']}")

        # Show common issues
        if result["common_issues"]:
            print(f"   🔧 Issues: {', '.join(result['common_issues'])}")

        if result["missing_env"]:
            print(f"   🔑 Missing env: {', '.join(result['missing_env'])}")

        if result["requires_api_key"]:
            print("   🔐 Requires API key")

        if result["is_external"]:
            external_count += 1

        if not result["enabled"]:
            print("   🔴 Disabled in config")

        # Count by tier
        if result["available"]:
            if result["tier"] == "essential":
                essential_count += 1
            elif result["tier"] == "useful":
                useful_count += 1
            elif result["tier"] == "advanced":
                advanced_count += 1

    print("=" * 80)
    print(f"📊 Summary: {available_count}/{len(diag_results)} servers available")
    if external_count > 0:
        print(f"🌐 External/Marketplace servers: {external_count}")
    print(f"   🔥 Essential: {essential_count}, ⚡ Useful: {useful_count}, 🚀 Advanced: {advanced_count}")
    print()


def get_free_servers(config: MCPConfig) -> dict[str, ServerConfig]:
    """Get servers that work without API keys and are available."""
    diag = diagnose_mcp_servers(config)
    free_servers = {}

    for name, result in diag.items():
        if result["available"] and not result["requires_api_key"]:
            free_servers[name] = config.servers[name]

    return free_servers
