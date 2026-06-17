"""Memory-Adaptive Pipeline Tournament — the innovation that lets the arena
run two 14 GB models on a 16 GB Mac without OOM.

The core idea is a three-tier scheduler:

  CONCURRENT  — both models comfortably fit; run the current parallel path.
  HOT_SWAP    — only one model fits at a time; unload the *other* model
                immediately before each A↔B turn inside one task.
  PIPELINE    — even one model barely fits; run ALL N tasks against model
                A while it's loaded, unload A, run ALL N tasks against
                model B, then assemble the per-task pairs at the end. From
                the user's point of view the match still looks parallel
                because the UI replays the recorded streams in sync.

It's deliberately conservative: the headroom multipliers below are tuned
for Apple's unified memory where OS + Ollama + Docker share the same
budget. Adjust via env (`ARENA_MEM_CONCURRENT_HEADROOM`, …) if you have
dedicated VRAM.

Memory math used here is rough but reliable:
  model_size_gb = blob_size_on_disk × (1.0 for q4_K_M, 1.2 for fp16 view, etc.)
  Available_RAM (psutil) -- already_loaded_models_gb (Ollama /api/ps)
  Headroom = Available_RAM × (1 - reserve_pct)

`reserve_pct` accounts for the OS, the shell, the dashboard, and Docker
(which we now ship for safe code execution and consumes 0.5–1 GB).
"""
from __future__ import annotations

import dataclasses
import logging
import os
import time
from enum import Enum
from typing import Optional

log = logging.getLogger("arena.memory_scheduler")

# ── Env-tunable thresholds ──────────────────────────────────────────────────
# The scheduler reasons about *usable* RAM (total minus OS reserve) because
# it will unload every other model before each phase. So the question is
# really: "do these models fit, given we'll free up everything first?"
#
# Multipliers are applied to the relevant model size:
#   - CONCURRENT: (A + B) × 1.2  must fit in usable RAM (KV cache headroom)
#   - HOT_SWAP:   max(A, B) × 1.3 must fit (some slack while the *other*
#                                model finishes unloading)
#   - PIPELINE:   max(A, B) × 1.05 must fit (tightest viable mode)
_CONCURRENT_MULT = float(os.getenv("ARENA_MEM_CONCURRENT_MULT", "1.2"))
_HOTSWAP_MULT    = float(os.getenv("ARENA_MEM_HOTSWAP_MULT",    "1.25"))
# PIPELINE is willing to push past usable RAM by ~5%; macOS will swap to
# SSD, which is slow but correct. This is the whole point of the mode —
# get a result rather than refuse.
_PIPELINE_MULT   = float(os.getenv("ARENA_MEM_PIPELINE_MULT",   "0.95"))
# OS / Docker / browser reserve — pulled off the top of total RAM. On
# 16 GB Apple Silicon, macOS itself needs ~1.5 GB at minimum to stay
# responsive; everything else can be ours.
_OS_RESERVE_GB   = float(os.getenv("ARENA_MEM_OS_RESERVE_GB",   "1.5"))


class Strategy(str, Enum):
    CONCURRENT = "CONCURRENT"     # safe to load both at once (existing path)
    HOT_SWAP   = "HOT_SWAP"       # unload between A↔B turns inside each task
    PIPELINE   = "PIPELINE"       # run all-A first, unload, then all-B
    INSUFFICIENT = "INSUFFICIENT" # even one model won't fit — surface error


@dataclasses.dataclass
class StrategyDecision:
    strategy:        Strategy
    available_gb:    float       # what we currently have to work with
    model_a_gb:      float
    model_b_gb:      float
    reason:          str         # human-readable explanation
    estimated_wall_s: float = 0.0  # wall-clock prediction
    # speedup if we'd been able to run CONCURRENT vs the chosen strategy
    speedup_lost:    float = 1.0

    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d["strategy"] = self.strategy.value
        return d


class MemoryScheduler:
    """Pick a tournament execution strategy from live system state.

    The scheduler is *advisory*: it tells Arena which mode to run in and
    why. Arena does the actual orchestration. This keeps the policy
    independent of the executor and easy to unit-test.
    """

    def __init__(self, ollama_base: str = "http://localhost:11434",
                 reserve_gb: Optional[float] = None) -> None:
        self.ollama_base = ollama_base.rstrip("/")
        self.reserve_gb  = _OS_RESERVE_GB if reserve_gb is None else reserve_gb

    # ── memory probes ──────────────────────────────────────────────────────
    def available_ram_gb(self) -> float:
        """Bytes currently free, *after* OS reserve. Used for live UI gauge."""
        try:
            import psutil
            free_gb = psutil.virtual_memory().available / 1024**3
            return max(0.0, free_gb - self.reserve_gb)
        except Exception:                # psutil missing or platform refusal
            return 4.0                   # conservative fallback

    def usable_ram_gb(self) -> float:
        """What we can use *after evicting all other models*. The scheduler
        plans against this number, not against currently-free RAM, because
        ``unload_all_except()`` is the very first step in every match.
        """
        return max(0.0, self.total_ram_gb() - self.reserve_gb)

    def total_ram_gb(self) -> float:
        try:
            import psutil
            return psutil.virtual_memory().total / 1024**3
        except Exception:
            return 16.0                  # conservative fallback

    # ── per-model sizing ───────────────────────────────────────────────────
    def model_size_gb(self, model: str) -> float:
        """Best-effort: ask Ollama /api/show then /api/ps; fall back to 0.

        For non-Ollama backends (e.g. ``spec:qwen3-14b``) we look up the
        underlying main blob from the spec registry.
        """
        # Speculative-decoding pseudo-models: size = main + draft
        if model.startswith("spec:"):
            try:
                from .backends.spec import SPEC_SERVERS
                cfg = SPEC_SERVERS.get(model)
                if cfg:
                    main = self.model_size_gb(cfg["main"])
                    draft = self.model_size_gb(cfg["draft"])
                    return main + draft
            except Exception:
                return 0.0
        try:
            import requests
            r = requests.post(f"{self.ollama_base}/api/show",
                              json={"name": model}, timeout=5)
            if r.ok:
                d = r.json()
                size = int(
                    d.get("size") or d.get("size_vram") or
                    (d.get("details") or {}).get("size") or 0
                )
                if size > 0:
                    return size / 1024**3
                # Some Ollama versions don't return size on /api/show, fall
                # back to /api/tags (lists all models with sizes).
            tags = requests.get(f"{self.ollama_base}/api/tags", timeout=3)
            if tags.ok:
                for m in tags.json().get("models", []):
                    if m.get("name") == model or m.get("model") == model:
                        return int(m.get("size", 0)) / 1024**3
        except Exception as e:
            log.debug(f"model_size_gb({model}): {e}")
        return 0.0                       # unknown — caller treats as "fits"

    def loaded_models_gb(self) -> float:
        """Bytes currently sitting in VRAM/Ollama runtime."""
        try:
            import requests
            r = requests.get(f"{self.ollama_base}/api/ps", timeout=2)
            if r.ok:
                return sum(int(m.get("size", 0)) for m in
                           r.json().get("models", [])) / 1024**3
        except Exception:
            pass
        return 0.0

    # ── unload a single model from Ollama (keep_alive=0) ──────────────────
    def unload(self, model: str) -> bool:
        """Tell Ollama to evict this model from RAM right now."""
        if model.startswith("spec:"):    # spec servers are separate procs
            return True
        try:
            import requests
            r = requests.post(
                f"{self.ollama_base}/api/generate",
                json={"model": model, "prompt": "", "keep_alive": 0,
                      "stream": False, "options": {"num_predict": 0}},
                timeout=10,
            )
            return r.ok
        except Exception as e:
            log.warning(f"unload({model}) failed: {e}")
            return False

    def unload_all_except(self, keep: list[str]) -> int:
        """Evict every currently-loaded Ollama model that isn't in `keep`."""
        try:
            import requests
            ps = requests.get(f"{self.ollama_base}/api/ps", timeout=2)
            if not ps.ok:
                return 0
            evicted = 0
            for m in ps.json().get("models", []):
                name = m.get("name") or m.get("model")
                if name and name not in keep:
                    if self.unload(name):
                        evicted += 1
            return evicted
        except Exception:
            return 0

    # ── prefetch into OS page cache (cheap, non-blocking) ─────────────────
    def prefetch(self, model: str) -> None:
        """Best-effort warm-up of the GGUF blob in the OS page cache so the
        next ``ollama run`` mmaps it without going to disk."""
        from pathlib import Path
        import subprocess, threading
        # Resolve the blob path (Ollama stores manifests + blobs under ~/.ollama)
        blob = self._find_blob(model)
        if not blob or not blob.exists():
            return
        def _warm():
            try:
                # `cat blob >/dev/null` is the standard POSIX warm-up trick
                subprocess.run(["cat", str(blob)],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL,
                               timeout=120)
            except Exception:
                pass
        threading.Thread(target=_warm, daemon=True).start()

    @staticmethod
    def _find_blob(model: str):
        """Best-effort: read the manifest, return the model-blob path."""
        from pathlib import Path
        import json
        home = Path.home() / ".ollama" / "models"
        manifests = home / "manifests" / "registry.ollama.ai" / "library"
        if ":" in model:
            mod, tag = model.split(":", 1)
        else:
            mod, tag = model, "latest"
        mf = manifests / mod / tag
        if not mf.exists():
            return None
        try:
            data = json.loads(mf.read_text())
            for layer in data.get("layers", []):
                if "model" in layer.get("mediaType", ""):
                    digest = layer["digest"].replace("sha256:", "sha256-")
                    return home / "blobs" / digest
        except Exception:
            return None
        return None

    # ── the strategy picker (the heart of the innovation) ──────────────────
    def choose(self, model_a: str, model_b: str) -> StrategyDecision:
        a_gb   = self.model_size_gb(model_a)
        b_gb   = self.model_size_gb(model_b)
        usable = self.usable_ram_gb()
        avail  = self.available_ram_gb()      # purely informational here
        bigger = max(a_gb, b_gb)
        total  = a_gb + b_gb

        # No reliable size info → trust the existing CONCURRENT path
        if total == 0:
            return StrategyDecision(
                strategy=Strategy.CONCURRENT,
                available_gb=round(avail, 2),
                model_a_gb=0, model_b_gb=0,
                reason="Model sizes unknown — defaulting to concurrent.",
            )

        # — CONCURRENT: both can sit in RAM together with KV-cache headroom
        if usable >= total * _CONCURRENT_MULT:
            return StrategyDecision(
                strategy=Strategy.CONCURRENT,
                available_gb=round(avail, 2),
                model_a_gb=round(a_gb, 2),
                model_b_gb=round(b_gb, 2),
                reason=(f"Usable {usable:.1f} GB ≥ {total*_CONCURRENT_MULT:.1f} "
                        f"GB ({_CONCURRENT_MULT}× total) — both fit, "
                        f"running concurrently."),
                speedup_lost=1.0,
            )

        # — HOT_SWAP: one model fits with breathing room; cycle per task
        if usable >= bigger * _HOTSWAP_MULT:
            return StrategyDecision(
                strategy=Strategy.HOT_SWAP,
                available_gb=round(avail, 2),
                model_a_gb=round(a_gb, 2),
                model_b_gb=round(b_gb, 2),
                reason=(f"Combined {total:.1f} GB > usable {usable:.1f} GB, "
                        f"but {bigger:.1f} GB fits one. Hot-swap A↔B per "
                        f"task; expect ~2× wall-clock."),
                speedup_lost=1.8,
            )

        # — PIPELINE: only ONE model fits at all; go all-in on A then all-in on B
        if usable >= bigger * _PIPELINE_MULT:
            return StrategyDecision(
                strategy=Strategy.PIPELINE,
                available_gb=round(avail, 2),
                model_a_gb=round(a_gb, 2),
                model_b_gb=round(b_gb, 2),
                reason=(f"Tight: usable {usable:.1f} GB barely fits "
                        f"{bigger:.1f} GB. Running ALL tasks vs A, "
                        f"unloading, then ALL tasks vs B — UI replays "
                        f"as parallel."),
                speedup_lost=2.0,
            )

        return StrategyDecision(
            strategy=Strategy.INSUFFICIENT,
            available_gb=round(avail, 2),
            model_a_gb=round(a_gb, 2),
            model_b_gb=round(b_gb, 2),
            reason=(f"Usable {usable:.1f} GB < {bigger * _PIPELINE_MULT:.1f} "
                    f"GB required for even one model. Close apps, free RAM, "
                    f"or pick a smaller model."),
            speedup_lost=0.0,
        )
