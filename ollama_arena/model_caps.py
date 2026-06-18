"""Model capability auto-detection via Ollama /api/show.

Detects per-model capabilities without storing them on disk — the cache lives
only for the process lifetime. Re-detection happens automatically if the model
list changes (new `detect()` call clears stale entries).

Detected capabilities
---------------------
- vision       : bool — model has a CLIP/image-embedding component
- tools        : bool — model advertises function-calling in its template
- ctx_length   : int  — context window size (tokens)
- families     : list[str] — e.g. ["llama", "clip"]
- param_size   : str  — e.g. "7B", "13B" (best-effort from name)
"""
from __future__ import annotations

import logging
import re
import threading
import time

log = logging.getLogger("arena.model_caps")

# Cache entries expire after this many seconds so re-pulled/updated models
# are re-probed automatically rather than serving stale capability flags.
_CACHE_TTL = 3600  # 1 hour

_cache: dict[str, dict] = {}   # model → caps dict
_cache_ts: dict[str, float] = {}  # model → insertion time
_lock = threading.Lock()

_PARAM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[Bb]")


def _param_size(name: str) -> str:
    m = _PARAM_RE.search(name)
    return f"{m.group(1)}B" if m else "?"


def _detect_one(model: str, ollama_url: str) -> dict:
    """Query /api/show and extract capability flags. Returns empty dict on error."""
    try:
        import requests
        resp = requests.post(
            f"{ollama_url.rstrip('/')}/api/show",
            json={"name": model},
            timeout=10,
        )
        if resp.status_code != 200:
            return {}
        info = resp.json()
    except Exception as e:
        log.debug(f"caps probe failed for {model!r}: {e}")
        return {}

    details = info.get("details", {})
    families: list[str] = []
    raw_families = details.get("families") or details.get("family") or []
    if isinstance(raw_families, str):
        raw_families = [raw_families]
    families = [f.lower() for f in raw_families]

    vision = "clip" in families or any("vision" in f for f in families)

    # Check modelfile template for tool-call markers
    modelfile: str = info.get("modelfile", "")
    tools = (
        "{{ .ToolCalls }}" in modelfile
        or "<tool_call>" in modelfile
        or '"tools"' in modelfile.lower()
    )

    ctx = (
        details.get("context_length")
        or info.get("model_info", {}).get("llama.context_length")
        or 0
    )
    try:
        ctx = int(ctx)
    except (TypeError, ValueError):
        ctx = 0

    return {
        "vision": vision,
        "tools": tools,
        "ctx_length": ctx,
        "families": families,
        "param_size": _param_size(model),
    }


def get(model: str, ollama_url: str = "http://localhost:11434") -> dict:
    """Return cached capability dict, re-detecting when the TTL has expired."""
    now = time.time()
    with _lock:
        if model in _cache and now - _cache_ts.get(model, 0) < _CACHE_TTL:
            return _cache[model]
    caps = _detect_one(model, ollama_url)
    with _lock:
        _cache[model] = caps
        _cache_ts[model] = now
    return caps


def detect_all(models: list[str], ollama_url: str = "http://localhost:11434") -> dict[str, dict]:
    """Detect capabilities for every model in the list, in parallel threads."""
    results: dict[str, dict] = {}

    def _worker(m: str) -> None:
        results[m] = get(m, ollama_url)

    threads = [threading.Thread(target=_worker, args=(m,), daemon=True) for m in models]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    return results


def invalidate(model: str | None = None) -> None:
    """Remove a single model (or all) from the cache."""
    with _lock:
        if model is None:
            _cache.clear()
            _cache_ts.clear()
        else:
            _cache.pop(model, None)
            _cache_ts.pop(model, None)
