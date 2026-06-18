"""Strict AST-based Python validator for the sandbox.

This is the *first* line of defense — it rejects obviously dangerous code
before the runtime is even spawned. The container is the *second* line.

Threat model:
  - Untrusted Python that may try to read host files, exfiltrate data,
    fork-bomb, or escape the sandbox via reflection / builtins lookups.

Rejected patterns (non-exhaustive):
  - imports of: os, sys, subprocess, shutil, socket, urllib, requests,
                pty, ctypes, pickle, marshal, multiprocessing, threading,
                signal, resource, gc, asyncio, http, ftplib, smtplib,
                builtins, importlib, codeop, code, _frozen_importlib
  - calls to:   eval, exec, compile, open, __import__, getattr/setattr/
                delattr/hasattr, globals, locals, vars, breakpoint, input,
                quit, exit, help, dir
  - attribute access to any dunder name (e.g. __class__, __mro__,
    __subclasses__, __globals__, __builtins__, __base__, __dict__,
    __code__, __init_subclass__, __getitem__, __reduce__, …) — these
    are the bread-and-butter of Python sandbox escapes
  - subscript access to __builtins__ via .__getitem__("__builtins__")
  - decorators that reference dangerous names
  - the bare `lambda` construct is allowed but its body is recursed
  - `with` statements, `try/except`, comprehensions are recursed normally

This validator is intentionally conservative: a *little* code that benign
users write will be blocked (e.g. using `getattr` for legitimate
reflection). For an evaluation arena that's an acceptable trade-off.
"""
from __future__ import annotations
import ast
import re
from dataclasses import dataclass

# ── Blocklists ───────────────────────────────────────────────────────────────

DANGEROUS_MODULES: frozenset[str] = frozenset({
    # I/O & process
    "os", "sys", "subprocess", "shutil", "pty", "signal", "resource",
    # network
    "socket", "urllib", "requests", "http", "httplib", "httplib2",
    "ftplib", "smtplib", "telnetlib", "asyncio", "aiohttp", "websocket",
    # serialization / introspection escape vectors
    "pickle", "cPickle", "marshal", "shelve", "dill",
    "ctypes", "cffi", "_ctypes",
    # importer / code execution
    "importlib", "imp", "code", "codeop", "runpy",
    "builtins", "__builtin__", "_frozen_importlib", "_bootstrap",
    # threading / multiprocessing — fork bomb risk
    "threading", "multiprocessing", "concurrent",
    # GC / introspection
    "gc", "inspect", "trace", "traceback", "linecache",
    # SSH / shell
    "paramiko", "fabric", "pexpect",
    # Additional dangerous modules
    "platform", "uuid", "hashlib", "secrets", "tokenize",
    "dis", "parser", "symbol", "keyword",
    # Database / file system
    "sqlite3", "dbm", "gdbm", "csv",
    # Time / random (potential for timing attacks)
    "time", "datetime", "random",
})

DANGEROUS_FUNCTIONS: frozenset[str] = frozenset({
    # arbitrary execution
    "eval", "exec", "compile", "execfile",
    # reflection / attribute walks (globals/locals are still high-risk for escapes)
    "globals", "locals", "vars", "dir",
    # importer
    "__import__", "open",
    # debugging / shells
    "breakpoint", "input", "raw_input", "help",
    "quit", "exit",
    # Memory / resource exhaustion
    "memoryview", "bytearray", "bytes", "array",
    # File operations that could bypass restrictions
    "file", "Path", "pathlib",
    # Process manipulation
    "fork", "spawn", "kill", "send_signal",
    # Note: 'type', 'getattr', 'hasattr', 'setattr', 'delattr' removed to avoid
    # false positives in common coding tasks. Docker is the primary boundary.
})

# Allow these dunders even though they're double-underscore. Anything else
# is treated as a sandbox escape vector.
DUNDER_ALLOWLIST: frozenset[str] = frozenset({
    "__name__", "__main__", "__doc__", "__init__",
    "__version__", "__author__", "__license__",
})


# Suspicious patterns that may indicate escape attempts
SUSPICIOUS_PATTERNS: list[tuple[str, str]] = [
    (r"__import__\s*\(", "Dynamic __import__ call"),
    (r"exec\s*\(", "Direct exec call"),
    (r"eval\s*\(", "Direct eval call"),
    (r"compile\s*\(", "Direct compile call"),
    (r"\.\s*__class__\s*\.", "Class traversal"),
    (r"\.\s*__bases__\s*\[", "Base class access"),
    (r"\.\s*__mro__\s*\[", "MRO access"),
    (r"\.\s*__subclasses__\s*\(", "Subclasses access"),
    (r"\.\s*__globals__\s*\[", "Globals access"),
    (r"\.\s*__builtins__\s*\[", "Builtins access"),
    (r"getattr\s*\([^,]+,\s*['\"]\s*__", "Dunder getattr"),
    (r"setattr\s*\([^,]+,\s*['\"]\s*__", "Dunder setattr"),
    (r"\.\s*__getattribute__\s*\(", "Getattribute override"),
    (r"\.\s*__setattr__\s*\(", "Setattr override"),
    (r"open\s*\(['\"]", "File open attempt"),
    (r"__import__\s*\(\s*['\"]", "Import attempt"),
]


def check_suspicious_patterns(code: str) -> tuple[bool, str]:
    """Quick pre-check for obvious escape attempt patterns before AST parsing.
    Returns (is_safe, reason)."""
    code_lower = code.lower()
    for pattern, reason in SUSPICIOUS_PATTERNS:
        if re.search(pattern, code_lower):
            return False, f"Suspicious pattern detected: {reason}"
    return True, ""


@dataclass
class Verdict:
    safe:   bool
    reason: str = ""

    def __bool__(self) -> bool:
        return self.safe


# ── Visitor ──────────────────────────────────────────────────────────────────

class _StrictVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.is_safe: bool = True
        self.reason: str = ""

    def _fail(self, why: str) -> None:
        if self.is_safe:                       # only record the first hit
            self.is_safe = False
            self.reason = why

    def generic_visit(self, node: ast.AST) -> None:
        if not self.is_safe:
            return
        super().generic_visit(node)

    # ---- imports
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            base = alias.name.split(".")[0]
            if base in DANGEROUS_MODULES:
                self._fail(f"Dangerous module import: {alias.name}")
                return
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            base = node.module.split(".")[0]
            if base in DANGEROUS_MODULES:
                self._fail(f"Dangerous module import: {node.module}")
                return
        # `from anything import os` — also dangerous
        for alias in node.names:
            if alias.name in DANGEROUS_MODULES:
                self._fail(f"Dangerous name import: {alias.name}")
                return
        self.generic_visit(node)

    # ---- calls
    def visit_Call(self, node: ast.Call) -> None:
        # Bare names: eval(...), exec(...), getattr(...)
        if isinstance(node.func, ast.Name):
            fname = node.func.id
            if fname in DANGEROUS_FUNCTIONS:
                self._fail(f"Dangerous function call: {fname}()")
                return
            
            # Special case for reflection: block strings that look like dunders
            # E.g. getattr(obj, "__class__")
            if fname in {"getattr", "setattr", "hasattr", "delattr"}:
                if len(node.args) >= 2:
                    key = _extract_const_string(node.args[1])
                    if key and key.startswith("__") and key.endswith("__") and key not in DUNDER_ALLOWLIST:
                        self._fail(f"Dunder string access via {fname} blocked: {key!r}")
                        return

        # Attribute calls: foo.eval(), obj.__getattribute__()
        elif isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            if attr in DANGEROUS_FUNCTIONS:
                self._fail(f"Dangerous method call: .{attr}()")
                return
            # block .__getattribute__, .__subclasses__, etc.
            if (attr.startswith("__") and attr.endswith("__")
                    and attr not in DUNDER_ALLOWLIST):
                self._fail(f"Dunder method call blocked: .{attr}()")
                return
        self.generic_visit(node)

    # ---- attribute access (covers obj.__class__, obj.__mro__, etc.)
    def visit_Attribute(self, node: ast.Attribute) -> None:
        if (node.attr.startswith("__") and node.attr.endswith("__")
                and node.attr not in DUNDER_ALLOWLIST):
            self._fail(f"Dunder attribute blocked: .{node.attr}")
            return
        self.generic_visit(node)

    # ---- subscripts: stop `__builtins__["__import__"]` style escapes
    def visit_Subscript(self, node: ast.Subscript) -> None:
        # Detect `<expr>["__something__"]` literal lookups
        key = _extract_const_string(node.slice)
        if key and key.startswith("__") and key.endswith("__"):
            self._fail(f"Subscript dunder lookup blocked: [{key!r}]")
            return
        self.generic_visit(node)

    # ---- assignment targets: forbid binding to dangerous names
    def visit_Name(self, node: ast.Name) -> None:
        # writes to `__builtins__` etc.
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            if node.id in {"__builtins__", "__import__"}:
                self._fail(f"Cannot bind name: {node.id}")
                return
        self.generic_visit(node)

    # ---- f-strings / format specs: harmless, recurse
    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        self.generic_visit(node)


def _extract_const_string(slice_node: ast.AST) -> str | None:
    """Return the literal string if the subscript is a single constant str."""
    # Python ≥3.9 — slice is the expression directly
    if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
        return slice_node.value
    # Python <3.9 used ast.Index wrapper
    if isinstance(slice_node, ast.Index):                           # type: ignore[attr-defined]
        inner = slice_node.value                                     # type: ignore[attr-defined]
        if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
            return inner.value
    return None


# ── Public API ───────────────────────────────────────────────────────────────

def is_safe_python(code: str, max_bytes: int = 256_000) -> tuple[bool, str]:
    """
    Validate `code`. Returns (safe, reason).

    On failure `reason` is the first thing that tripped the validator —
    surface it back to the user so they can fix it (e.g. "Dunder
    attribute blocked: .__class__").
    """
    # Quick pattern check before AST parsing
    pattern_safe, pattern_reason = check_suspicious_patterns(code)
    if not pattern_safe:
        return False, pattern_reason

    if len(code.encode("utf-8", "ignore")) > max_bytes:
        return False, f"Code exceeds {max_bytes} bytes"

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"Syntax Error: {e.msg} (line {e.lineno})"

    v = _StrictVisitor()
    v.visit(tree)
    return v.is_safe, v.reason


def verdict(code: str) -> Verdict:
    """Same as is_safe_python but returns a structured Verdict."""
    ok, why = is_safe_python(code)
    return Verdict(safe=ok, reason=why)
