"""Safe Python code execution sandbox with timeout and output capture."""
from __future__ import annotations
import io, re, sys, threading
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import dataclass

_BLOCKED = [
    r"\brm\s+-rf\b", r"\bshutil\.rmtree\b", r"\bos\.remove\s*\(",
    r"\bsubprocess\b", r"\bsocket\b", r"\burllib\b", r"\brequests\b",
    r"\bopen\s*\([^)]*['\"]w['\"]",  # file write
    r"__import__\s*\(['\"]os['\"]",
    r"\beval\s*\(.*input", r"\bexec\s*\(.*input",
]


def _is_safe(code: str) -> tuple[bool, str]:
    for pat in _BLOCKED:
        if re.search(pat, code, re.IGNORECASE):
            return False, pat
    return True, ""


@dataclass
class RunResult:
    accepted: bool
    output: str
    error: str
    timed_out: bool = False


def run_with_tests(code: str, test_code: str, timeout_sec: int = 10) -> RunResult:
    """Execute code + test_code in a restricted namespace. Returns RunResult."""
    safe, reason = _is_safe(code + "\n" + test_code)
    if not safe:
        return RunResult(accepted=False, output="", error=f"BLOCKED: {reason}")

    full = code + "\n" + test_code
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    holder: dict = {"ok": False, "error": ""}

    def _run():
        try:
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                exec(compile(full, "<arena>", "exec"), {"__builtins__": __builtins__})
            holder["ok"] = True
        except AssertionError as e:
            holder["error"] = f"AssertionError: {e}"
        except Exception as e:
            holder["error"] = f"{type(e).__name__}: {e}"

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=timeout_sec)
    if t.is_alive():
        return RunResult(accepted=False, output="", error="Timeout", timed_out=True)

    return RunResult(
        accepted=holder["ok"],
        output=stdout_buf.getvalue()[:500],
        error=holder["error"],
    )
