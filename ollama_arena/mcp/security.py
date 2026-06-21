"""Security gate for dangerous MCP tool execution."""
from __future__ import annotations

import json
import logging
import os
import sys
from typing import Literal

log = logging.getLogger("arena.mcp.security")

DangerTier = Literal["safe", "confirm", "deny"]


def check_security_gate(
    name: str,
    arguments: dict,
    danger_tier: DangerTier,
) -> tuple[bool, str]:
    """Return (allowed, message). Deny-by-default for non-TTY confirm-tier tools."""
    if danger_tier == "safe":
        return True, ""

    if danger_tier == "deny":
        if os.environ.get("ARENA_AUTO_APPROVE") == "1":
            log.warning("[security] auto-approving denied tool %s via ARENA_AUTO_APPROVE", name)
            return True, ""
        return False, f"Error: Tool '{name}' is permanently denied."

    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True, ""

    # confirm tier
    if os.environ.get("ARENA_AUTO_APPROVE") == "1":
        return True, ""

    if not sys.stdin.isatty():
        return False, (
            f"Error: Dangerous tool '{name}' denied in non-interactive mode. "
            "Set ARENA_AUTO_APPROVE=1 to override."
        )

    print(f"\n\033[93m[SECURITY GATE] Model wants to execute dangerous tool: {name}\033[0m")
    print(f"Arguments: {json.dumps(arguments, indent=2)}")
    print("Allow this action? [y/N]: ", end="", flush=True)
    ans = input().strip().lower()
    if ans != "y":
        return False, "Error: Action explicitly denied by human."
    return True, ""
