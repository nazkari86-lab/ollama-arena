"""AST sandbox validator — coverage for known escape vectors + benign code."""
import pytest
from ollama_arena.sandboxes.security import is_safe_python, verdict


# ── benign code must pass ────────────────────────────────────────────────────

@pytest.mark.parametrize("code", [
    "print('hello')",
    "def add(a, b): return a + b\nprint(add(1, 2))",
    "[x*x for x in range(10)]",
    "def fib(n): return n if n < 2 else fib(n-1) + fib(n-2)",
    "class Foo:\n    def __init__(self, x): self.x = x",
    "import math\nprint(math.sqrt(2))",
    "import json\nprint(json.dumps({'a': 1}))",
    "with open as ctx:\n    pass" if False else "x = [1,2,3]\nprint(sum(x))",
])
def test_allows_benign_code(code):
    ok, reason = is_safe_python(code)
    assert ok, f"benign code blocked: {reason}"


# ── reflection / introspection escape vectors ────────────────────────────────

@pytest.mark.parametrize("code", [
    "().__class__.__base__.__subclasses__()",
    "().__class__.__mro__",
    "(lambda: x.__class__.__base__)()",
    "x.__globals__",
    "x.__getattribute__('attr')",
    "{}.__class__.__bases__[0].__subclasses__()",
])
def test_blocks_reflection_escapes(code):
    ok, _ = is_safe_python(code)
    assert not ok, f"reflection escape NOT blocked: {code}"


# ── exec / eval / compile / open ─────────────────────────────────────────────

@pytest.mark.parametrize("code", [
    "eval('1+1')",
    "exec('x=1')",
    "compile('x=1', '<s>', 'exec')",
    "open('/etc/passwd')",
    "__import__('os')",
    "getattr(x, 'attr')",
    "setattr(x, 'a', 1)",
    "globals()",
    "breakpoint()",
    "input()",
])
def test_blocks_dangerous_functions(code):
    ok, reason = is_safe_python(code)
    assert not ok, f"NOT blocked: {code}"
    assert "Dangerous" in reason or "Dunder" in reason


# ── dangerous module imports ─────────────────────────────────────────────────

@pytest.mark.parametrize("mod", [
    "os", "sys", "subprocess", "shutil", "socket", "urllib", "requests",
    "pickle", "marshal", "ctypes", "threading", "multiprocessing",
    "importlib", "inspect", "gc", "signal", "resource",
])
def test_blocks_dangerous_imports(mod):
    ok, _ = is_safe_python(f"import {mod}")
    assert not ok, f"`import {mod}` NOT blocked"


@pytest.mark.parametrize("mod", [
    "os", "subprocess", "ctypes", "pickle",
])
def test_blocks_from_imports(mod):
    ok, _ = is_safe_python(f"from {mod} import something")
    assert not ok, f"`from {mod}` NOT blocked"


# ── subscript-based builtins lookup ──────────────────────────────────────────

@pytest.mark.parametrize("code", [
    'x["__builtins__"]',
    'x["__class__"]',
    'globals()["__builtins__"]["eval"]',     # also blocks globals() upfront
])
def test_blocks_subscript_dunder_lookups(code):
    ok, _ = is_safe_python(code)
    assert not ok


# ── source size limit ────────────────────────────────────────────────────────

def test_blocks_oversize_source():
    ok, reason = is_safe_python("x=1\n" * 100_000)
    assert not ok
    assert "exceeds" in reason.lower()


# ── Verdict object ───────────────────────────────────────────────────────────

def test_verdict_truthy_for_safe():
    v = verdict("x = 1 + 1")
    assert bool(v) is True
    assert v.safe is True


def test_verdict_falsy_for_unsafe():
    v = verdict("import os")
    assert bool(v) is False
    assert v.safe is False
    assert "os" in v.reason
