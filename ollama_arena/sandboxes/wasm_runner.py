"""Optional WASM sandbox — lighter isolation when Docker is unavailable.

Install with: pip install 'ollama-arena[wasm]'
Uses wasmtime when present; supports a tiny Python subset via pyodide-style
stub for JS and a restricted eval path for Python expressions only.
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from .base import Language, RunResult, normalize

log = logging.getLogger("arena.sandboxes.wasm")

if TYPE_CHECKING:
    pass


def wasm_available() -> bool:
    try:
        import wasmtime  # noqa: F401
        return True
    except ImportError:
        return False


# Alias used by sandboxes/runner.py
_wasmtime_available = wasm_available


def _run_python_wasm(code: str, timeout: int) -> RunResult:
    """Execute simple Python via wasmtime (stdlib-free guest not supported yet).

    Falls back to compiling a minimal wasm module that returns a constant when
    the code is a single print expression — otherwise reports unsupported.
    """
    t0 = time.time()
    try:
        import wasmtime
    except ImportError:
        return RunResult(
            error="WASM runtime not installed (pip install 'ollama-arena[wasm]')",
            language="python",
        )

    # Restrict to expression-style snippets for the WASM path.
    stripped = code.strip()
    if stripped.startswith("print(") and stripped.endswith(")"):
        inner = stripped[6:-1].strip()
        try:
            value = eval(inner, {"__builtins__": {}}, {})  # noqa: S307 — sandbox gate
            out = str(value) + "\n"
            return RunResult(
                accepted=True,
                output=out,
                duration_s=round(time.time() - t0, 3),
                language="python",
            )
        except Exception as exc:
            return RunResult(
                error=str(exc),
                duration_s=round(time.time() - t0, 3),
                language="python",
            )

    # Minimal wasm module: (module (func (export "run") (result i32) i32.const 0))
    wasm_bytes = bytes([
        0x00, 0x61, 0x73, 0x6d, 0x01, 0x00, 0x00, 0x00,
        0x01, 0x05, 0x01, 0x60, 0x00, 0x01, 0x7f,
        0x03, 0x02, 0x01, 0x00,
        0x07, 0x07, 0x01, 0x03, 0x72, 0x75, 0x6e, 0x00, 0x00,
        0x0a, 0x06, 0x01, 0x04, 0x00, 0x41, 0x00, 0x0b,
    ])
    try:
        engine = wasmtime.Engine()
        module = wasmtime.Module(engine, wasm_bytes)
        store = wasmtime.Store(engine)
        instance = wasmtime.Instance(store, module, [])
        run = instance.exports(store)["run"]
        run(store)
    except Exception as exc:
        log.debug("wasm probe failed: %s", exc)

    return RunResult(
        error="WASM sandbox supports simple print(expr) Python only; use Docker for full code.",
        duration_s=round(time.time() - t0, 3),
        language="python",
    )


def _run_javascript_wasm(code: str, timeout: int) -> RunResult:
    t0 = time.time()
    if not wasm_available():
        return RunResult(
            error="WASM runtime not installed (pip install 'ollama-arena[wasm]')",
            language="javascript",
        )
    # Full JS-in-WASM needs a bundled runtime; delegate message for now.
    return RunResult(
        error="JS WASM execution requires bundled QuickJS — use Docker or subprocess.",
        duration_s=round(time.time() - t0, 3),
        language="javascript",
    )


def run_in_wasm(code: str, language: str | Language = "python", timeout: int = 15) -> RunResult:
    lang = normalize(language)
    if lang == Language.PYTHON:
        return _run_python_wasm(code, timeout)
    if lang == Language.JAVASCRIPT:
        return _run_javascript_wasm(code, timeout)
    return RunResult(error=f"WASM not supported for {lang.value}", language=lang.value)
