"""Developer knowledge and code analysis tools."""
from __future__ import annotations

import ast
import json
import subprocess
from typing import Callable

from .web import ddg_search
from .workspace import WORKSPACE_DIR, _safe_path, SecurityError


def codebase_search(args: dict) -> str:
    pattern = args.get("pattern", "")
    if not pattern:
        return "Error: No pattern provided."
    try:
        res = subprocess.run(
            ["grep", "-rnE", pattern, str(WORKSPACE_DIR)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res.returncode == 0:
            lines = res.stdout.splitlines()[:50]
            return f"Codebase Search Results for '{pattern}':\n" + "\n".join(lines)
        return "No matches found or search error."
    except Exception as exc:
        return f"Search error: {exc}"


def ast_parse(args: dict) -> str:
    try:
        file_path = _safe_path(args.get("file_path", "").lstrip("/"))
        if not file_path.exists():
            return "Error: File not found."
        code = file_path.read_text()
        tree = ast.parse(code)
        funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        return json.dumps({"functions": funcs, "classes": classes}, indent=2)
    except SecurityError as exc:
        return f"Error: {exc}"
    except Exception as exc:
        return f"Error: {exc}"


def consult_expert(args: dict) -> str:
    topic = args.get("topic", "").lower()
    skills_db = {
        "debugging": (
            "Systematic Debugging: 1. Reproduce the failure. 2. Minimize test case. "
            "3. Formulate hypothesis. 4. Instrument code. 5. Fix. 6. Add regression test."
        ),
        "tdd": (
            "TDD Workflow: Red-Green-Refactor. Write failing test, minimal pass code, refactor."
        ),
        "security": (
            "Security Review: Validate inputs, parameterize SQL, encode output, Auth/Authz, "
            "never log secrets."
        ),
        "api_design": (
            "API Design: RESTful nouns, correct HTTP methods/status codes, pagination, rate limits."
        ),
        "git": (
            "Git Workflow: Conventional commits (feat:, fix:, chore:). Branch per feature."
        ),
        "database": (
            "Database Migrations: Write up/down migrations. Add, deprecate, then drop."
        ),
        "react": (
            "React Patterns: Hooks discipline, Server/Client boundaries, Suspense, a11y-first."
        ),
        "architecture": (
            "Hexagonal Architecture: Ports & Adapters, dependency inversion, testable use-cases."
        ),
    }
    for key, text in skills_db.items():
        if key in topic:
            return f"Expert Guideline ({key.upper()}):\n{text}"
    return f"Available expert topics: {', '.join(skills_db.keys())}."


def algo_docs(args: dict) -> str:
    topic = args.get("topic", "").lower()
    db = {
        "binary search": (
            "Binary Search: O(log n). Requires sorted array. Mid = L + (R-L)//2."
        ),
        "cap theorem": "CAP Theorem: Consistency, Availability, Partition Tolerance. Pick two.",
        "rate limiter": (
            "Rate Limiter: Token bucket, Leaky bucket, Fixed window, Sliding window log."
        ),
    }
    for key, value in db.items():
        if key in topic:
            return value
    return ddg_search({"query": f"{topic} algorithm system design"})


def ui_tars_action(args: dict) -> str:
    action = args.get("action", "")
    target = args.get("target", "")
    return (
        f"UI-TARS Action '{action}' on '{target}' executed via OS accessibility layer "
        "(mocked for text-only model context)."
    )


def tool_defs() -> list[tuple[str, Callable[[dict], str], dict, str]]:
    return [
        (
            "codebase_search",
            codebase_search,
            {
                "type": "function",
                "function": {
                    "name": "codebase_search",
                    "description": "Regex/grep search across the arena workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {"pattern": {"type": "string"}},
                        "required": ["pattern"],
                    },
                },
            },
            "confirm",
        ),
        (
            "ast_parse",
            ast_parse,
            {
                "type": "function",
                "function": {
                    "name": "ast_parse",
                    "description": "Return AST structure (classes, functions) of a Python file.",
                    "parameters": {
                        "type": "object",
                        "properties": {"file_path": {"type": "string"}},
                        "required": ["file_path"],
                    },
                },
            },
            "safe",
        ),
        (
            "consult_expert",
            consult_expert,
            {
                "type": "function",
                "function": {
                    "name": "consult_expert",
                    "description": "Consult senior engineering guidelines (TDD, security, etc.).",
                    "parameters": {
                        "type": "object",
                        "properties": {"topic": {"type": "string"}},
                        "required": ["topic"],
                    },
                },
            },
            "safe",
        ),
        (
            "algo_docs",
            algo_docs,
            {
                "type": "function",
                "function": {
                    "name": "algo_docs",
                    "description": "Fetch algorithm or system design pattern documentation.",
                    "parameters": {
                        "type": "object",
                        "properties": {"topic": {"type": "string"}},
                        "required": ["topic"],
                    },
                },
            },
            "safe",
        ),
        (
            "ui_tars_action",
            ui_tars_action,
            {
                "type": "function",
                "function": {
                    "name": "ui_tars_action",
                    "description": "UI-TARS desktop automation action bridge.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string"},
                            "target": {"type": "string"},
                        },
                        "required": ["action", "target"],
                    },
                },
            },
            "confirm",
        ),
    ]
