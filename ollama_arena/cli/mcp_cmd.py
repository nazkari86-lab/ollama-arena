"""MCP diagnostics and management commands."""
from __future__ import annotations

from .common import _console, print_success, print_error, print_warning


def cmd_mcp_diagnose(args):
    """Diagnose MCP server availability and configuration."""
    c = _console()
    from ..mcp_config import (
        load_mcp_config,
        diagnose_mcp_servers,
        print_server_diagnostics,
        get_free_servers,
    )

    config = load_mcp_config(args.config)

    # Print diagnostics
    diag_results = diagnose_mcp_servers(config)
    print_server_diagnostics(diag_results)

    # Show free servers
    free_servers = get_free_servers(config)
    print_success(f"✓ {len(free_servers)} servers work without API keys")
    for name in free_servers.keys():
        c.print(f"  - {name}")

    # Check configuration file location
    from ..mcp_config import _CONFIG_PATH
    c.print(f"\n📁 Config file: {_CONFIG_PATH}")
    c.print(f"📝 Total servers configured: {len(config.servers)}")

    # Show tier breakdown
    essential = config.get_servers_by_tier("essential")
    useful = config.get_servers_by_tier("useful")
    advanced = config.get_servers_by_tier("advanced")

    c.print(f"🔥 Essential servers: {len(essential)}")
    c.print(f"⚡ Useful servers: {len(useful)}")
    c.print(f"🚀 Advanced servers: {len(advanced)}")


def cmd_mcp_list(args):
    """List all configured MCP servers."""
    c = _console()
    from ..mcp_config import load_mcp_config

    config = load_mcp_config(args.config)

    c.print("\n📋 Configured MCP Servers:")
    print("=" * 80)

    for name, server_config in config.servers.items():
        status = "✅" if server_config.enabled else "🔴"
        tier_icon = {"essential": "🔥", "useful": "⚡", "advanced": "🚀"}.get(server_config.tier, "❔")
        api_key = "🔐" if server_config.requires_api_key else ""

        c.print(f"{status} {tier_icon} {api_key} {name:30} [{server_config.tier}]")
        c.print(f"   {server_config.description}")
        c.print(f"   Command: {server_config.command} {' '.join(server_config.args[:3])}{'...' if len(server_config.args) > 3 else ''}")
        if server_config.env:
            c.print(f"   Environment: {len(server_config.env)} variables set")
        c.print()


def cmd_mcp_enable(args):
    """Enable a specific MCP server."""
    from ..mcp_config import load_mcp_config, save_default_config, _CONFIG_PATH

    config = load_mcp_config(args.config)

    if args.server not in config.servers:
        print_error(f"Server '{args.server}' not found in configuration")
        return

    config.servers[args.server].enabled = True

    # Save updated config
    import json
    config_dict = {
        "servers": {
            name: {
                "command": cfg.command,
                "args": cfg.args,
                "description": cfg.description,
                "env": cfg.env,
                "tier": cfg.tier,
                "enabled": cfg.enabled,
                "requires_api_key": cfg.requires_api_key,
            }
            for name, cfg in config.servers.items()
        }
    }

    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(config_dict, indent=2))

    print_success(f"✓ Enabled MCP server: {args.server}")


def cmd_mcp_disable(args):
    """Disable a specific MCP server."""
    from ..mcp_config import load_mcp_config, save_default_config, _CONFIG_PATH

    config = load_mcp_config(args.config)

    if args.server not in config.servers:
        print_error(f"Server '{args.server}' not found in configuration")
        return

    config.servers[args.server].enabled = False

    # Save updated config
    import json
    config_dict = {
        "servers": {
            name: {
                "command": cfg.command,
                "args": cfg.args,
                "description": cfg.description,
                "env": cfg.env,
                "tier": cfg.tier,
                "enabled": cfg.enabled,
                "requires_api_key": cfg.requires_api_key,
            }
            for name, cfg in config.servers.items()
        }
    }

    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(config_dict, indent=2))

    print_success(f"✓ Disabled MCP server: {args.server}")


def cmd_mcp_install(args):
    """Install a new MCP server from a template or npm package."""
    c = _console()
    import subprocess
    from pathlib import Path

    # Simple installation of popular MCP servers
    server_templates = {
        "sqlite": ("uvx", ["mcp-server-sqlite"]),
        "filesystem": ("npx", ["-y", "@modelcontextprotocol/server-filesystem", str(Path.home() / "arena_workspace")]),
        "memory": ("npx", ["-y", "@modelcontextprotocol/server-memory"]),
        "git": ("npx", ["-y", "@modelcontextprotocol/server-git", "--repository", str(Path.cwd())]),
        "time": ("npx", ["-y", "@modelcontextprotocol/server-time"]),
    }

    if args.server in server_templates:
        command, server_args = server_templates[args.server]
        try:
            c.print(f"Installing MCP server: {args.server}")
            result = subprocess.run(
                [command] + server_args, capture_output=True, text=True, check=True, timeout=120,
            )
            print_success(f"✓ Successfully installed {args.server}")
        except subprocess.CalledProcessError as e:
            print_error(f"✗ Failed to install {args.server}: {e.stderr}")
        except subprocess.TimeoutExpired:
            print_error(f"✗ Failed to install {args.server}: timed out after 120s")
        except FileNotFoundError:
            print_error(f"✗ Failed to install {args.server}: '{command}' not found on PATH")
    else:
        print_error(f"Unknown server template: {args.server}")
        print(f"Available templates: {', '.join(server_templates.keys())}")
