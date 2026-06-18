"""Code execution tools."""
from __future__ import annotations

from typing import Callable

from ...sandboxes.runner import run_in_language


def code_interpreter(args: dict) -> str:
    code = args.get("code", "")
    language = args.get("language", "python")
    if not code:
        return "Error: No code provided."
    result = run_in_language(code, language=language, use_docker=True)
    if result.error:
        return f"Exit {result.exit_code}: {result.error}\n{result.output}"
    return result.output or "(no output)"


def tool_defs() -> list[tuple[str, Callable[[dict], str], dict, str]]:
    return [
        (
            "code_interpreter",
            code_interpreter,
            {
                "type": "function",
                "function": {
                    "name": "code_interpreter",
                    "description": "Execute Python/JS code in a Docker sandbox.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"},
                            "language": {"type": "string"},
                        },
                        "required": ["code"],
                    },
                },
            },
            "confirm",
        ),
    ]
