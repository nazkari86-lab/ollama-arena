"""Hardware-aware model fit scoring — unit tests."""
import unittest.mock as mock

import pytest

from ollama_arena.hardware_fit import (
    _fit_pct, hardware_summary, score_models, best_two_models,
)


# ── _fit_pct: agrees with memory_scheduler.py's own real thresholds ────────

def test_fit_pct_comfortable_headroom_is_100():
    assert _fit_pct(usable_gb=16, model_gb=8) == 100   # ratio 2.0


def test_fit_pct_at_concurrent_threshold_is_75():
    assert _fit_pct(usable_gb=12, model_gb=10) == 75   # ratio 1.2 == _CONCURRENT_MULT


def test_fit_pct_at_pipeline_threshold_is_40():
    assert _fit_pct(usable_gb=9.5, model_gb=10) == 40  # ratio 0.95 == _PIPELINE_MULT


def test_fit_pct_unrunnable_is_zero():
    assert _fit_pct(usable_gb=4, model_gb=20) == 0     # ratio 0.2


def test_fit_pct_zero_model_size_is_zero():
    assert _fit_pct(usable_gb=16, model_gb=0) == 0


def test_fit_pct_monotonic_in_ratio():
    """Fit score must never decrease as the usable/model ratio increases —
    a regression here would mean a smaller, easier-to-run model scores
    worse than a bigger one, which would be a real, user-visible bug."""
    ratios = [0.3, 0.6, 0.95, 1.1, 1.2, 1.4, 1.6, 2.0]
    scores = [_fit_pct(usable_gb=r * 10, model_gb=10) for r in ratios]
    assert scores == sorted(scores)


# ── hardware_summary: cheap psutil-only snapshot ────────────────────────────

def test_hardware_summary_shape():
    d = hardware_summary()
    assert set(d) == {"platform", "machine", "cpu", "cpu_count",
                       "total_ram_gb", "usable_ram_gb"}
    assert d["total_ram_gb"] > 0
    assert d["cpu_count"] >= 1


# ── score_models: end-to-end with mocked Ollama + perf history ─────────────

def _tags_response(models):
    """models: list of (name, size_bytes, family)."""
    resp = mock.Mock()
    resp.ok = True
    resp.raise_for_status = mock.Mock()
    resp.json.return_value = {
        "models": [
            {"name": n, "size": s, "details": {"family": f}}
            for n, s, f in models
        ]
    }
    return resp


@pytest.fixture
def mock_ollama_models():
    """Two real chat models + one embedding model that must be excluded."""
    return [
        ("small:1b", 1_000_000_000, "llama"),     # ~0.93 GB blob
        ("big:7b", 7_000_000_000, "qwen2"),       # ~6.5 GB blob
        ("nomic-embed-text:latest", 300_000_000, "nomic-bert"),
    ]


def test_score_models_excludes_embedding_models(mock_ollama_models):
    with mock.patch("requests.get", return_value=_tags_response(mock_ollama_models)), \
         mock.patch("ollama_arena.performance.PerfTracker.stats", return_value=[]):
        results = score_models()
    names = {r["model"] for r in results}
    assert "nomic-embed-text:latest" not in names
    assert names == {"small:1b", "big:7b"}


def test_score_models_smaller_model_fits_better(mock_ollama_models):
    """On a memory-constrained machine, the smaller model must score a
    higher (or equal) fit than the bigger one."""
    with mock.patch("requests.get", return_value=_tags_response(mock_ollama_models)), \
         mock.patch("ollama_arena.performance.PerfTracker.stats", return_value=[]), \
         mock.patch("ollama_arena.memory_scheduler.MemoryScheduler.usable_ram_gb",
                     return_value=4.0):
        results = score_models()
    by_name = {r["model"]: r for r in results}
    assert by_name["small:1b"]["fit_pct"] >= by_name["big:7b"]["fit_pct"]


def test_score_models_uses_measured_tps_when_available(mock_ollama_models):
    perf = [{"model": "small:1b", "n_samples": 10, "tps_mean": 42.0}]
    with mock.patch("requests.get", return_value=_tags_response(mock_ollama_models)), \
         mock.patch("ollama_arena.performance.PerfTracker.stats", return_value=perf):
        results = score_models()
    row = next(r for r in results if r["model"] == "small:1b")
    assert row["tps"] == 42.0
    assert row["tps_kind"] == "measured"


def test_score_models_estimates_unmeasured_tps_from_reference(mock_ollama_models):
    """big:7b has no history; small:1b does. Since big:7b is the larger
    (heavier) model, its estimated tps must be lower than small:1b's
    measured tps -- this is the core memory-bandwidth-bound scaling
    assumption the estimator is built on."""
    perf = [{"model": "small:1b", "n_samples": 10, "tps_mean": 40.0}]
    with mock.patch("requests.get", return_value=_tags_response(mock_ollama_models)), \
         mock.patch("ollama_arena.performance.PerfTracker.stats", return_value=perf):
        results = score_models()
    by_name = {r["model"]: r for r in results}
    assert by_name["big:7b"]["tps_kind"] == "estimated"
    assert by_name["big:7b"]["tps"] < by_name["small:1b"]["tps"]


def test_score_models_unknown_tps_when_no_history_at_all(mock_ollama_models):
    """No model has ever been benchmarked -- must honestly report unknown
    rather than inventing a number with no basis (same principle as the
    MPSMonitor honest-estimate fix elsewhere in this codebase)."""
    with mock.patch("requests.get", return_value=_tags_response(mock_ollama_models)), \
         mock.patch("ollama_arena.performance.PerfTracker.stats", return_value=[]):
        results = score_models()
    assert all(r["tps"] is None and r["tps_kind"] == "unknown" for r in results)


def test_score_models_handles_ollama_offline_gracefully(mock_ollama_models):
    with mock.patch("requests.get", side_effect=ConnectionError("offline")):
        results = score_models()
    assert results == []


def test_best_two_models_returns_top_two_by_fit_then_speed(mock_ollama_models):
    perf = [
        {"model": "small:1b", "n_samples": 10, "tps_mean": 40.0},
        {"model": "big:7b", "n_samples": 10, "tps_mean": 5.0},
    ]
    with mock.patch("requests.get", return_value=_tags_response(mock_ollama_models)), \
         mock.patch("ollama_arena.performance.PerfTracker.stats", return_value=perf):
        top2 = best_two_models()
    assert top2 == ["small:1b", "big:7b"]


def test_best_two_models_fewer_than_two_installed():
    with mock.patch("requests.get",
                     return_value=_tags_response([("only:1b", 1_000_000_000, "llama")])), \
         mock.patch("ollama_arena.performance.PerfTracker.stats", return_value=[]):
        top2 = best_two_models()
    assert top2 == ["only:1b"]
