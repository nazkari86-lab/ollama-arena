"""Workspace-scoped filesystem tools with path containment."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

WORKSPACE_DIR = Path.home() / "arena_workspace"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


class SecurityError(Exception):
    """Raised when a workspace path escapes the sandbox root."""


def _safe_path(rel: str) -> Path:
    rel = (rel or ".").lstrip("/")
    target = (WORKSPACE_DIR / rel).resolve()
    root = WORKSPACE_DIR.resolve()
    if target != root and root not in target.parents:
        raise SecurityError("Path escape attempt")
    return target


def ls(args: dict) -> str:
    try:
        target = _safe_path(args.get("path", "."))
        if not target.exists():
            return "Error: Path not found."
        if target.is_file():
            return target.name
        return "\n".join(sorted(os.listdir(target))) or "(empty)"
    except SecurityError as exc:
        return f"Error: {exc}"
    except Exception as exc:
        return f"Error: {exc}"


def read_file(args: dict) -> str:
    try:
        target = _safe_path(args.get("path", ""))
        if not target.exists():
            return "Error: File not found."
        return target.read_text()
    except SecurityError as exc:
        return f"Error: {exc}"
    except Exception as exc:
        return f"Error: {exc}"


def write_file(args: dict) -> str:
    try:
        target = _safe_path(args.get("path", ""))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(args.get("content", ""))
        return f"Wrote {len(args.get('content', ''))} bytes to {target.relative_to(WORKSPACE_DIR)}"
    except SecurityError as exc:
        return f"Error: {exc}"
    except Exception as exc:
        return f"Error: {exc}"


def tool_defs() -> list[tuple[str, Callable[[dict], str], dict, str]]:
    return [
        (
            "ls",
            ls,
            {
                "type": "function",
                "function": {
                    "name": "ls",
                    "description": "List files in the arena workspace directory.",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                    },
                },
            },
            "safe",
        ),
        (
            "read_file",
            read_file,
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file from the arena workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    },
                },
            },
            "confirm",
        ),
        (
            "write_file",
            write_file,
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write content to a file in the arena workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                        },
                        "required": ["path", "content"],
                    },
                },
            },
            "confirm",
        ),
    ]
