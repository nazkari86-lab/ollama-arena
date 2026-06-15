"""
Universal multi-language sandbox runner.

Uses native compilers/interpreters via subprocess with strict timeouts.
For stronger isolation, set use_docker=True (requires docker installed).
"""
from __future__ import annotations
import os, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path

from .base import Language, RunResult, normalize


# ── Static security filter ───────────────────────────────────────────────────
_BLOCKED_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bsudo\b",
    r"\bshutil\.rmtree\s*\(\s*['\"]?/",
    r"\bos\.remove\s*\(\s*['\"]?/",
    r"\bsubprocess\.(?:Popen|run|call)\(.*shell\s*=\s*True",
    r"\bsocket\.\w+\(",
    r"\brequests\.",
    r"\burllib\.request\.",
    r"\bfetch\s*\(['\"]https?://",
    r"\beval\s*\(.*input",
    r"\bnp\.fromfile\(['\"]?/etc",
    r"\bchild_process\b",
    r"\bnet\.connect\b",
]


def _check_safe(code: str) -> tuple[bool, str]:
    for pat in _BLOCKED_PATTERNS:
        if re.search(pat, code, re.IGNORECASE):
            return False, pat
    return True, ""


# ── Runtime detection ────────────────────────────────────────────────────────
def _has(cmd: str) -> bool:
    return shutil.which(cmd) is not None


_RUNTIME_CHECKS: dict[Language, list[str]] = {
    Language.PYTHON:     ["python3", "python"],
    Language.JAVASCRIPT: ["node"],
    Language.TYPESCRIPT: ["tsx", "ts-node", "deno"],
    Language.RUST:       ["rustc"],
    Language.GO:         ["go"],
    Language.CPP:        ["g++", "clang++"],
    Language.BASH:       ["bash", "sh"],
}


def available_languages() -> list[str]:
    """Languages whose runtime is installed on this system."""
    out = []
    for lang, cands in _RUNTIME_CHECKS.items():
        if any(_has(c) for c in cands):
            out.append(lang.value)
    return out


# ── Language-specific runners ────────────────────────────────────────────────
def _run_python(code: str, timeout: int, tmp: Path) -> RunResult:
    f = tmp / "main.py"
    f.write_text(code)
    py = "python3" if _has("python3") else "python"
    return _exec([py, str(f)], timeout, Language.PYTHON)


def _run_javascript(code: str, timeout: int, tmp: Path) -> RunResult:
    f = tmp / "main.js"
    f.write_text(code)
    return _exec(["node", str(f)], timeout, Language.JAVASCRIPT)


def _run_typescript(code: str, timeout: int, tmp: Path) -> RunResult:
    f = tmp / "main.ts"
    f.write_text(code)
    if _has("tsx"):
        return _exec(["tsx", str(f)], timeout, Language.TYPESCRIPT)
    if _has("ts-node"):
        return _exec(["ts-node", "--transpile-only", str(f)], timeout, Language.TYPESCRIPT)
    if _has("deno"):
        return _exec(["deno", "run", "--quiet", str(f)], timeout, Language.TYPESCRIPT)
    return RunResult(error="TypeScript runner missing (install: npm i -g tsx)",
                     language="typescript")


def _run_rust(code: str, timeout: int, tmp: Path) -> RunResult:
    src = tmp / "main.rs"
    bin_path = tmp / "main"
    src.write_text(code)
    # Compile (no network, edition=2021)
    cc = subprocess.run(
        ["rustc", "--edition=2021", "-O", str(src), "-o", str(bin_path)],
        capture_output=True, text=True, timeout=min(timeout, 30),
    )
    if cc.returncode != 0:
        return RunResult(error=cc.stderr[:500], exit_code=cc.returncode,
                         language="rust")
    return _exec([str(bin_path)], timeout, Language.RUST)


def _run_go(code: str, timeout: int, tmp: Path) -> RunResult:
    f = tmp / "main.go"
    f.write_text(code)
    return _exec(["go", "run", str(f)], timeout, Language.GO)


def _run_cpp(code: str, timeout: int, tmp: Path) -> RunResult:
    src = tmp / "main.cpp"
    bin_path = tmp / "main"
    src.write_text(code)
    compiler = "g++" if _has("g++") else "clang++"
    cc = subprocess.run(
        [compiler, "-O2", "-std=c++17", str(src), "-o", str(bin_path)],
        capture_output=True, text=True, timeout=min(timeout, 30),
    )
    if cc.returncode != 0:
        return RunResult(error=cc.stderr[:500], exit_code=cc.returncode,
                         language="cpp")
    return _exec([str(bin_path)], timeout, Language.CPP)


def _run_bash(code: str, timeout: int, tmp: Path) -> RunResult:
    return _exec(["bash", "-c", code], timeout, Language.BASH)


_RUNNERS = {
    Language.PYTHON:     _run_python,
    Language.JAVASCRIPT: _run_javascript,
    Language.TYPESCRIPT: _run_typescript,
    Language.RUST:       _run_rust,
    Language.GO:         _run_go,
    Language.CPP:        _run_cpp,
    Language.BASH:       _run_bash,
}


# ── Core executor ────────────────────────────────────────────────────────────
def _exec(cmd: list[str], timeout: int, lang: Language) -> RunResult:
    """Run subprocess with timeout and capture I/O."""
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        return RunResult(
            accepted=(proc.returncode == 0),
            output=proc.stdout[:2000],
            error=proc.stderr[:1000],
            exit_code=proc.returncode,
            duration_s=round(time.time() - t0, 3),
            language=lang.value,
        )
    except subprocess.TimeoutExpired:
        return RunResult(error="Timeout", timed_out=True,
                         duration_s=float(timeout), language=lang.value)
    except FileNotFoundError as e:
        return RunResult(error=f"Runtime not found: {e}",
                         duration_s=round(time.time() - t0, 3),
                         language=lang.value)
    except Exception as e:
        return RunResult(error=f"{type(e).__name__}: {e}",
                         duration_s=round(time.time() - t0, 3),
                         language=lang.value)


# ── Docker isolation (optional) ──────────────────────────────────────────────
_DOCKER_IMAGES = {
    Language.PYTHON:     "python:3.12-slim",
    Language.JAVASCRIPT: "node:20-alpine",
    Language.TYPESCRIPT: "node:20-alpine",
    Language.RUST:       "rust:1.78-slim",
    Language.GO:         "golang:1.22-alpine",
    Language.CPP:        "gcc:13-bookworm",
    Language.BASH:       "alpine:3.20",
}


def _run_in_docker(code: str, lang: Language, timeout: int) -> RunResult:
    """Run code in an isolated docker container (read-only, no network)."""
    if not _has("docker"):
        return RunResult(error="Docker not installed", language=lang.value)
    image = _DOCKER_IMAGES[lang]
    ext = {"python":"py","javascript":"js","typescript":"ts",
           "rust":"rs","go":"go","cpp":"cpp","bash":"sh"}[lang.value]
    cmd_map = {
        Language.PYTHON:     ["python3", "/code/main.py"],
        Language.JAVASCRIPT: ["node",    "/code/main.js"],
        Language.TYPESCRIPT: ["sh", "-c", "npx -y tsx /code/main.ts"],
        Language.RUST:       ["sh", "-c", "rustc --edition=2021 -O /code/main.rs -o /tmp/m && /tmp/m"],
        Language.GO:         ["go", "run", "/code/main.go"],
        Language.CPP:        ["sh", "-c", "g++ -O2 -std=c++17 /code/main.cpp -o /tmp/m && /tmp/m"],
        Language.BASH:       ["bash", "/code/main.sh"],
    }
    with tempfile.TemporaryDirectory() as tmp:
        tp = Path(tmp)
        (tp / f"main.{ext}").write_text(code)
        t0 = time.time()
        proc = subprocess.run(
            ["docker", "run", "--rm",
             "--network=none",
             "--memory=512m", "--cpus=1",
             "--read-only", "--tmpfs=/tmp:rw,size=64m",
             "-v", f"{tmp}:/code:ro",
             "-w", "/code",
             image] + cmd_map[lang],
            capture_output=True, text=True, timeout=timeout,
        )
        return RunResult(
            accepted=(proc.returncode == 0),
            output=proc.stdout[:2000],
            error=proc.stderr[:1000],
            exit_code=proc.returncode,
            duration_s=round(time.time() - t0, 3),
            language=lang.value,
        )


# ── Public API ───────────────────────────────────────────────────────────────
def run_in_language(
    code: str,
    language: str | Language = "python",
    timeout: int = 15,
    use_docker: bool = False,
) -> RunResult:
    """
    Execute `code` in the given language.

    Args:
        code:       Source to run.
        language:   Name or Language enum.
        timeout:    Seconds before kill.
        use_docker: If True, run in a docker sandbox (stronger isolation).

    Returns:
        RunResult with output, error, exit_code, duration.
    """
    lang = normalize(language)
    safe, pat = _check_safe(code)
    if not safe:
        return RunResult(blocked=True, error=f"BLOCKED: {pat}", language=lang.value)

    if use_docker:
        return _run_in_docker(code, lang, timeout)

    runner = _RUNNERS.get(lang)
    if not runner:
        return RunResult(error=f"Language not supported: {lang}", language=lang.value)

    with tempfile.TemporaryDirectory(prefix="arena_") as tmp:
        return runner(code, timeout, Path(tmp))
