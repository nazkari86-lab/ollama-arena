"""Hardware-aware model fit scoring — answers "how well will model X run on
*this* machine" as a 0-100 score, plus an estimated tokens/sec.

Deliberately reuses the exact RAM-sizing math `memory_scheduler.py` already
uses to decide CONCURRENT/HOT_SWAP/PIPELINE for real matches (same
``_PIPELINE_MULT``/``_CONCURRENT_MULT`` thresholds), so a model's fit score
here always agrees with what ``/api/strategy`` would actually do if you
picked it — one source of truth for "does this fit", not two competing
formulas.

Tokens/sec is either real measured data (``PerfTracker``, if the model has
been benchmarked on this machine before) or, for a model that's never been
run, an estimate *scaled from the user's own fastest-measured model* using
the standard memory-bandwidth-bound relationship for autoregressive decode
(tps scales ~inversely with effective model size on the same hardware).
This deliberately avoids guessing an absolute memory-bandwidth number we
have no reliable way to measure cross-platform (see telemetry/bandwidth.py
and telemetry/base.py's HardwareDetector docstrings for the real gaps:
Apple Silicon unified memory isn't reported by system_profiler, AMD VRAM
parsing is a dead code path, NVIDIA needs pynvml). If there's no measured
data for *any* model yet, tps is honestly reported as unknown rather than
inventing a number with no basis — same principle as the MPSMonitor power
estimate fix elsewhere in this codebase.
"""
from __future__ import annotations

import logging
import os
import platform as _platform

from .memory_scheduler import (
    MemoryScheduler,
    estimate_vram_gb,
    _CONCURRENT_MULT,
    _PIPELINE_MULT,
)
from .performance import PerfTracker

log = logging.getLogger("arena.hardware_fit")

# Below this fit ratio a model is considered effectively unrunnable on this
# machine (heavy swapping / OOM territory) — floor the score at 0 rather
# than letting the linear interpolation go negative.
_UNRUNNABLE_RATIO = 0.5
# Above this ratio there's so much headroom that finer distinctions don't
# matter to a user picking a model — cap the score at 100.
_COMFORTABLE_RATIO = 1.5

# Ollama's architecture-family names for embedding-only models (no
# autoregressive decoder, just a pooling head) — confirmed via /api/show's
# details.family for nomic-embed-text ("nomic-bert") and bge-m3 ("bert").
# These can't meaningfully be scored for "tokens/sec of generated text" or
# picked as an Arena Match contender, so they're excluded from scoring
# entirely rather than silently winning "best fit" for being tiny.
_EMBEDDING_FAMILIES = {"bert", "nomic-bert"}


def hardware_summary(ollama_url: str = "http://localhost:11434") -> dict:
    """Cheap, reliable hardware snapshot. Deliberately CPU/RAM-only via
    psutil + the stdlib ``platform`` module — no GPU-vendor shell-outs
    (rocm-smi/system_profiler/pynvml), since those are slow, sometimes
    require extra deps, and (per HardwareDetector's own docstrings) don't
    reliably report VRAM on Apple Silicon or AMD anyway. RAM is what the
    fit-scoring below actually depends on.
    """
    sched = MemoryScheduler(ollama_url)
    try:
        import psutil
        cpu_count = psutil.cpu_count(logical=True) or os.cpu_count() or 1
    except Exception:
        cpu_count = os.cpu_count() or 1
    return {
        "platform": _platform.system(),
        "machine": _platform.machine(),
        "cpu": _platform.processor() or _platform.machine(),
        "cpu_count": cpu_count,
        "total_ram_gb": round(sched.total_ram_gb(), 1),
        "usable_ram_gb": round(sched.usable_ram_gb(), 1),
    }


def _fit_pct(usable_gb: float, model_gb: float) -> int:
    """0-100 fit score, piecewise-linear between the scheduler's own real
    thresholds: ratio>=1.5 -> 100, ratio==_CONCURRENT_MULT(1.2) -> 75,
    ratio==_PIPELINE_MULT(0.95) -> 40, ratio<=0.5 -> 0."""
    if model_gb <= 0:
        return 0
    ratio = usable_gb / model_gb
    if ratio >= _COMFORTABLE_RATIO:
        return 100
    if ratio >= _CONCURRENT_MULT:
        span = _COMFORTABLE_RATIO - _CONCURRENT_MULT
        return round(75 + (ratio - _CONCURRENT_MULT) / span * 25)
    if ratio >= _PIPELINE_MULT:
        span = _CONCURRENT_MULT - _PIPELINE_MULT
        return round(40 + (ratio - _PIPELINE_MULT) / span * 35)
    if ratio >= _UNRUNNABLE_RATIO:
        span = _PIPELINE_MULT - _UNRUNNABLE_RATIO
        return round((ratio - _UNRUNNABLE_RATIO) / span * 40)
    return 0


def _list_models_with_blob_gb(ollama_url: str) -> list[tuple[str, float]]:
    """One /api/tags call -> (name, blob_gb) for every installed
    *generative* model. Avoids the per-model-HTTP-call-in-a-loop trap that
    previously made api_models() block for up to 10s x N models (fixed
    earlier in web.py) -- this scoring pass must not reintroduce that
    pattern, so family info is read from this same bulk response too
    (Ollama's /api/tags already includes details.family per model).
    Embedding-only models (see _EMBEDDING_FAMILIES) are skipped: they can't
    be scored for generation speed or picked as an Arena Match contender.
    """
    import requests
    try:
        r = requests.get(f"{ollama_url.rstrip('/')}/api/tags", timeout=5)
        r.raise_for_status()
    except Exception as e:
        log.warning(f"hardware_fit: /api/tags failed: {e}")
        return []
    out = []
    for m in r.json().get("models", []):
        name = m.get("name") or m.get("model")
        size = m.get("size", 0)
        family = (m.get("details") or {}).get("family", "")
        if name and size and family not in _EMBEDDING_FAMILIES:
            out.append((name, int(size) / 1024**3))
    return out


def score_models(ollama_url: str = "http://localhost:11434",
                  db_path: str = "arena.db") -> list[dict]:
    """Fit score (0-100) + tokens/sec for every installed model, sorted
    best-fit-first (ties broken by estimated speed)."""
    sched = MemoryScheduler(ollama_url)
    usable = sched.usable_ram_gb()
    perf_by_model = {p["model"]: p for p in PerfTracker(db_path=db_path).stats()}

    models_blob = _list_models_with_blob_gb(ollama_url)
    eff_gb_by_name = {name: estimate_vram_gb(blob_gb, name) for name, blob_gb in models_blob}

    reference = max(perf_by_model.values(), key=lambda p: p["n_samples"], default=None)
    ref_eff_gb = eff_gb_by_name.get(reference["model"]) if reference else None

    results = []
    for name, eff_gb in eff_gb_by_name.items():
        fit_pct = _fit_pct(usable, eff_gb)
        measured = perf_by_model.get(name)
        if measured:
            tps_value, tps_kind = measured["tps_mean"], "measured"
        elif reference and ref_eff_gb and eff_gb > 0:
            tps_value = round(reference["tps_mean"] * (ref_eff_gb / eff_gb), 1)
            tps_kind = "estimated"
        else:
            tps_value, tps_kind = None, "unknown"
        results.append({
            "model": name,
            "effective_size_gb": round(eff_gb, 2),
            "fit_pct": fit_pct,
            "tps": tps_value,
            "tps_kind": tps_kind,
        })
    return sorted(results, key=lambda r: (-r["fit_pct"], -(r["tps"] or 0)))


def best_two_models(ollama_url: str = "http://localhost:11434",
                     db_path: str = "arena.db") -> list[str]:
    """The two best-fitting models, for use as the default Arena Match
    pre-selection. Empty/single-element if fewer than 2 models are
    installed or scoreable."""
    scored = score_models(ollama_url, db_path=db_path)
    return [r["model"] for r in scored[:2]]
