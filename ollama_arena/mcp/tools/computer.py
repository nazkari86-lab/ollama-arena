"""Host computer automation tools (macOS)."""
from __future__ import annotations

import platform
import subprocess
from pathlib import Path
from typing import Callable


def computer_screenshot(args: dict) -> str:
    path = Path("/tmp/arena_screenshot.png")
    try:
        if platform.system() == "Darwin":
            subprocess.run(["screencapture", "-x", str(path)], check=True)
            return f"Screenshot saved to {path}."
        return "Screenshot not supported on this OS."
    except Exception as exc:
        return f"Error: {exc}"


def computer_click(args: dict) -> str:
    x, y = args.get("x", 0), args.get("y", 0)
    try:
        x_int, y_int = int(x), int(y)
    except (TypeError, ValueError):
        return "Error: x and y must be integers."
    try:
        if platform.system() == "Darwin":
            subprocess.run(
                ["osascript", "-e", f'tell application "System Events" to click at {{{x_int}, {y_int}}}'],
                check=True,
            )
            return f"Clicked at ({x_int}, {y_int})"
        return "Clicking not supported on this OS."
    except Exception as exc:
        return f"Error: {exc}"


def computer_type(args: dict) -> str:
    text = args.get("text", "")
    try:
        if platform.system() == "Darwin":
            escaped = text.replace('"', '\\"')
            subprocess.run(
                ["osascript", "-e", f'tell application "System Events" to keystroke "{escaped}"'],
                check=True,
            )
            return f"Typed '{text}'"
        return "Typing not supported on this OS."
    except Exception as exc:
        return f"Error: {exc}"


def tool_defs() -> list[tuple[str, Callable[[dict], str], dict, str]]:
    return [
        (
            "computer_screenshot",
            computer_screenshot,
            {
                "type": "function",
                "function": {
                    "name": "computer_screenshot",
                    "description": "Capture the host screen (macOS screencapture).",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            "confirm",
        ),
        (
            "computer_click",
            computer_click,
            {
                "type": "function",
                "function": {
                    "name": "computer_click",
                    "description": "Click at screen coordinates (x, y).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "integer"},
                            "y": {"type": "integer"},
                        },
                        "required": ["x", "y"],
                    },
                },
            },
            "confirm",
        ),
        (
            "computer_type",
            computer_type,
            {
                "type": "function",
                "function": {
                    "name": "computer_type",
                    "description": "Type text via keyboard automation.",
                    "parameters": {
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"],
                    },
                },
            },
            "confirm",
        ),
    ]
