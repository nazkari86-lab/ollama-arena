"""Git repository tools scoped to the arena workspace."""
from __future__ import annotations

import subprocess
from typing import Callable

from .workspace import WORKSPACE_DIR


def _git(args: list[str]) -> str:
    try:
        res = subprocess.run(
            ["git", *args],
            cwd=WORKSPACE_DIR,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if res.returncode != 0:
            return f"Git error: {res.stderr.strip() or res.stdout.strip()}"
        return res.stdout.strip() or "OK"
    except Exception as exc:
        return f"Error: {exc}"


def git_status(args: dict) -> str:
    return _git(["status", "--short"])


def git_commit(args: dict) -> str:
    message = args.get("message", "")
    if not message:
        return "Error: commit message required."
    stage = _git(["add", "-A"])
    if stage.startswith("Git error") or stage.startswith("Error:"):
        return stage
    return _git(["commit", "-m", message])


def tool_defs() -> list[tuple[str, Callable[[dict], str], dict, str]]:
    return [
        (
            "git_status",
            git_status,
            {
                "type": "function",
                "function": {
                    "name": "git_status",
                    "description": "Show git status in the arena workspace.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            "safe",
        ),
        (
            "git_commit",
            git_commit,
            {
                "type": "function",
                "function": {
                    "name": "git_commit",
                    "description": "Stage all changes and commit in the arena workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {"message": {"type": "string"}},
                        "required": ["message"],
                    },
                },
            },
            "confirm",
        ),
    ]
