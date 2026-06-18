"""Memory-Adaptive Pipeline Tournament scheduler — unit tests."""
import os
import unittest.mock as mock

import pytest

from ollama_arena.memory_scheduler import (
    MemoryScheduler, Strategy, StrategyDecision,
    parse_quantization, estimate_vram_gb,
)


@pytest.fixture
def sched():
    return MemoryScheduler()


def _pick(sched, a_gb, b_gb, total_gb, avail_gb=None):
    """Drive the picker with mocked sizes."""
    if avail_gb is None:
        avail_gb = total_gb / 2
    with mock.patch.object(sched, "model_size_gb",
                           side_effect=lambda m: a_gb if m == "A" else b_gb), \
         mock.patch.object(sched, "total_ram_gb",     return_value=total_gb), \
         mock.patch.object(sched, "available_ram_gb", return_value=avail_gb):
        return sched.choose("A", "B")


# ── core strategy table ──────────────────────────────────────────────────────

def test_concurrent_when_both_fit_comfortably(sched):
    d = _pick(sched, a_gb=2, b_gb=2, total_gb=16)
    assert d.strategy is Strategy.CONCURRENT


def test_hot_swap_when_one_fits(sched):
    d = _pick(sched, a_gb=8, b_gb=8, total_gb=16)
    assert d.strategy is Strategy.HOT_SWAP


def test_pipeline_for_users_14gb_x2_on_16gb_mac(sched):
    """The exact user scenario from the bug report."""
    d = _pick(sched, a_gb=14, b_gb=14, total_gb=16)
    assert d.strategy is Strategy.PIPELINE, (
        f"expected PIPELINE for 14+14 on 16, got {d.strategy.value}: {d.reason}"
    )


def test_insufficient_when_model_too_big(sched):
    d = _pick(sched, a_gb=20, b_gb=20, total_gb=16)
    assert d.strategy is Strategy.INSUFFICIENT


def test_unknown_sizes_fallback_to_concurrent(sched):
    d = _pick(sched, a_gb=0, b_gb=0, total_gb=16)
    assert d.strategy is Strategy.CONCURRENT
    assert "unknown" in d.reason.lower()


# ── decision payload shape ──────────────────────────────────────────────────

def test_decision_has_all_fields(sched):
    d = _pick(sched, a_gb=4, b_gb=4, total_gb=16)
    payload = d.to_dict()
    for k in ("strategy", "available_gb", "model_a_gb", "model_b_gb",
              "reason", "estimated_wall_s", "speedup_lost"):
        assert k in payload
    assert payload["strategy"] in {"CONCURRENT", "HOT_SWAP", "PIPELINE", "INSUFFICIENT"}


def test_speedup_lost_grows_with_strictness(sched):
    """Pipeline should report higher speedup loss than concurrent."""
    conc = _pick(sched, a_gb=2, b_gb=2,  total_gb=32)
    pipe = _pick(sched, a_gb=14, b_gb=14, total_gb=16)
    assert pipe.speedup_lost > conc.speedup_lost


# ── env-tunables actually tune ──────────────────────────────────────────────

def test_pipeline_mult_env_tunable(monkeypatch):
    monkeypatch.setenv("ARENA_MEM_PIPELINE_MULT", "2.0")  # extra strict
    # Reload module so threshold reads new env var
    import importlib, ollama_arena.memory_scheduler as ms
    importlib.reload(ms)
    s = ms.MemoryScheduler()
    d = _pick(s, a_gb=14, b_gb=14, total_gb=16)
    # 14 × 2.0 = 28 > 14.5 usable → INSUFFICIENT
    assert d.strategy is ms.Strategy.INSUFFICIENT
    monkeypatch.delenv("ARENA_MEM_PIPELINE_MULT", raising=False)
    importlib.reload(ms)


def test_quant_multiplier_from_tag():
    from ollama_arena.memory_scheduler import parse_quantization, quant_multiplier, estimate_vram_gb
    assert parse_quantization("llama3:8b-q4_K_M") == "q4_k_m"
    assert quant_multiplier("mistral:7b-q8_0") == 1.45
    est = estimate_vram_gb(4.0, "llama3:8b-q4_K_M", num_ctx=4096)
    assert est > 4.0  # weights + KV cache


def test_model_size_uses_vram_estimate(sched):
    with __import__("unittest").mock.patch.object(sched, "blob_size_gb", return_value=8.0):
        size = sched.model_size_gb("test:7b-q4_K_M")
        assert size >= 8.0


# ── unload bookkeeping ──────────────────────────────────────────────────────

def test_unload_handles_spec_models(sched):
    # spec: models live in their own llama-server, not Ollama; treat as no-op
    assert sched.unload("spec:qwen3-14b") is True


def test_unload_ollama_failure_returns_false(sched):
    with mock.patch("requests.post", side_effect=Exception("connection refused")):
        assert sched.unload("foo:bar") is False


# ── prefetch (best-effort; just must not raise) ────────────────────────────

def test_prefetch_does_not_raise_on_missing_blob(sched):
    sched.prefetch("nonexistent:tag")    # should be a no-op


def test_vram_estimate_payload(sched):
    with mock.patch.object(sched, "blob_size_gb", return_value=8.0):
        payload = sched.vram_estimate("llama3:8b-q4_k_m")
    assert payload["blob_gb"] == 8.0
    assert payload["estimated_vram_gb"] > 0
