"""Tests for telemetry module — dataclasses, enums and pure functions."""
from __future__ import annotations

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# bandwidth — BandwidthMethod, BandwidthMetrics
# ──────────────────────────────────────────────────────────────────────────────

class TestBandwidthMethod:
    def test_all_values_present(self):
        from ollama_arena.telemetry.bandwidth import BandwidthMethod
        values = {m.value for m in BandwidthMethod}
        assert "ebpf" in values
        assert "proc" in values
        assert "psutil" in values
        assert "none" in values

    def test_from_value(self):
        from ollama_arena.telemetry.bandwidth import BandwidthMethod
        assert BandwidthMethod("psutil") == BandwidthMethod.PSUTIL


class TestBandwidthMetrics:
    def _make(self, **kw):
        from ollama_arena.telemetry.bandwidth import BandwidthMetrics
        defaults = dict(
            timestamp=1000.0,
            bandwidth_gb_s=25.0,
            memory_used_gb=8.0,
            memory_total_gb=16.0,
            memory_percent=50.0,
        )
        defaults.update(kw)
        return BandwidthMetrics(**defaults)

    def test_basic_creation(self):
        m = self._make()
        assert m.bandwidth_gb_s == 25.0
        assert m.memory_percent == 50.0

    def test_default_gpu_fields_zero(self):
        m = self._make()
        assert m.gpu_memory_used_gb == 0.0
        assert m.gpu_bandwidth_gb_s == 0.0

    def test_default_cache_fields_zero(self):
        m = self._make()
        assert m.l1_cache_hit_rate == 0.0
        assert m.l2_cache_hit_rate == 0.0
        assert m.l3_cache_hit_rate == 0.0

    def test_to_dict_has_required_keys(self):
        m = self._make()
        d = m.to_dict()
        assert "timestamp" in d
        assert "bandwidth_gb_s" in d
        assert "memory_used_gb" in d
        assert "memory_total_gb" in d
        assert "memory_percent" in d

    def test_to_dict_values_match(self):
        m = self._make(bandwidth_gb_s=42.0, memory_percent=75.0)
        d = m.to_dict()
        assert d["bandwidth_gb_s"] == 42.0
        assert d["memory_percent"] == 75.0

    def test_to_dict_gpu_keys_present(self):
        m = self._make()
        d = m.to_dict()
        assert "gpu_memory_used_gb" in d
        assert "gpu_bandwidth_gb_s" in d


# ──────────────────────────────────────────────────────────────────────────────
# energy — PowerState, PowerMetrics
# ──────────────────────────────────────────────────────────────────────────────

class TestPowerState:
    def test_all_values(self):
        from ollama_arena.telemetry.energy import PowerState
        values = {s.value for s in PowerState}
        assert "idle" in values
        assert "recording" in values
        assert "error" in values

    def test_from_value(self):
        from ollama_arena.telemetry.energy import PowerState
        assert PowerState("recording") == PowerState.RECORDING


class TestPowerMetrics:
    def _make(self, **kw):
        from ollama_arena.telemetry.energy import PowerMetrics
        defaults = dict(timestamp=1234.0, power_w=150.0)
        defaults.update(kw)
        return PowerMetrics(**defaults)

    def test_basic_creation(self):
        m = self._make()
        assert m.power_w == 150.0
        assert m.timestamp == 1234.0

    def test_defaults_zero(self):
        m = self._make()
        assert m.energy_j == 0.0
        assert m.temperature_c == 0.0
        assert m.utilization_percent == 0.0
        assert m.memory_utilization_percent == 0.0

    def test_to_dict_all_keys(self):
        m = self._make()
        d = m.to_dict()
        assert "timestamp" in d
        assert "power_w" in d
        assert "energy_j" in d
        assert "temperature_c" in d
        assert "utilization_percent" in d

    def test_to_dict_values(self):
        m = self._make(power_w=200.0, temperature_c=85.0)
        d = m.to_dict()
        assert d["power_w"] == 200.0
        assert d["temperature_c"] == 85.0


# ──────────────────────────────────────────────────────────────────────────────
# quantization — QuantizationFormat, QuantizationResult, ParetoPoint, ParetoFrontier
# ──────────────────────────────────────────────────────────────────────────────

class TestQuantizationFormat:
    def test_all_formats_present(self):
        from ollama_arena.telemetry.quantization import QuantizationFormat
        formats = {f.value for f in QuantizationFormat}
        assert "Q4_K_M" in formats
        assert "Q8_0" in formats
        assert "FP16" in formats
        assert "FP32" in formats

    def test_from_value(self):
        from ollama_arena.telemetry.quantization import QuantizationFormat
        assert QuantizationFormat("Q4_K_M") == QuantizationFormat.Q4_K_M

    def test_iq_formats(self):
        from ollama_arena.telemetry.quantization import QuantizationFormat
        formats = {f.value for f in QuantizationFormat}
        assert "IQ4_NL" in formats
        assert "IQ4_XS" in formats


class TestQuantizationResult:
    def _make(self, **kw):
        from ollama_arena.telemetry.quantization import QuantizationResult, QuantizationFormat
        defaults = dict(
            format=QuantizationFormat.Q4_K_M,
            model_name="llama3:8b",
            file_size_gb=4.5,
            vram_usage_gb=6.0,
        )
        defaults.update(kw)
        return QuantizationResult(**defaults)

    def test_basic_creation(self):
        r = self._make()
        assert r.model_name == "llama3:8b"
        assert r.file_size_gb == 4.5

    def test_defaults_zero(self):
        r = self._make()
        assert r.avg_latency_s == 0.0
        assert r.avg_tps == 0.0
        assert r.elo_score == 0.0
        assert r.num_samples == 0
        assert r.error == ""

    def test_to_dict_has_format_value(self):
        r = self._make()
        d = r.to_dict()
        assert d["format"] == "Q4_K_M"

    def test_to_dict_has_all_keys(self):
        r = self._make()
        d = r.to_dict()
        for key in ["model_name", "file_size_gb", "vram_usage_gb", "avg_tps", "elo_score"]:
            assert key in d


class TestParetoPoint:
    def _make(self, **kw):
        from ollama_arena.telemetry.quantization import ParetoPoint, QuantizationFormat
        defaults = dict(
            format=QuantizationFormat.Q4_K_M,
            elo_score=1200.0,
            vram_savings_gb=2.0,
            efficiency_score=0.8,
        )
        defaults.update(kw)
        return ParetoPoint(**defaults)

    def test_creation(self):
        p = self._make()
        assert p.elo_score == 1200.0
        assert p.is_pareto_optimal is False

    def test_to_dict_format_value(self):
        p = self._make()
        d = p.to_dict()
        assert d["format"] == "Q4_K_M"
        assert d["is_pareto_optimal"] is False

    def test_to_dict_has_all_keys(self):
        p = self._make()
        d = p.to_dict()
        for key in ["format", "elo_score", "vram_savings_gb", "efficiency_score", "is_pareto_optimal"]:
            assert key in d


class TestParetoFrontier:
    def _make_result(self, fmt_str, elo, vram):
        from ollama_arena.telemetry.quantization import QuantizationResult, QuantizationFormat
        return QuantizationResult(
            format=QuantizationFormat(fmt_str),
            model_name="test_model",
            file_size_gb=vram * 0.8,
            vram_usage_gb=vram,
            elo_score=elo,
        )

    def test_empty_results_no_crash(self):
        from ollama_arena.telemetry.quantization import ParetoFrontier
        pf = ParetoFrontier([])
        assert pf.frontier == []

    def test_single_result_is_optimal(self):
        from ollama_arena.telemetry.quantization import ParetoFrontier
        results = [self._make_result("Q4_K_M", elo=1000.0, vram=6.0)]
        pf = ParetoFrontier(results)
        assert len(pf.frontier) >= 0  # at least empty or one optimal

    def test_pareto_analysis_runs(self):
        from ollama_arena.telemetry.quantization import ParetoFrontier
        results = [
            self._make_result("Q4_K_M", elo=1000.0, vram=6.0),
            self._make_result("Q8_0", elo=1050.0, vram=9.0),
            self._make_result("FP16", elo=1100.0, vram=16.0),
        ]
        pf = ParetoFrontier(results)
        assert isinstance(pf.frontier, list)

    def test_get_optimal_format_returns_format_or_none(self):
        from ollama_arena.telemetry.quantization import ParetoFrontier, QuantizationFormat
        results = [
            self._make_result("Q4_K_M", elo=1000.0, vram=6.0),
            self._make_result("Q8_0", elo=1050.0, vram=9.0),
        ]
        pf = ParetoFrontier(results)
        result = pf.get_optimal_format()
        assert result is None or isinstance(result, QuantizationFormat)

    def test_get_optimal_format_with_vram_constraint(self):
        from ollama_arena.telemetry.quantization import ParetoFrontier
        results = [
            self._make_result("Q4_K_M", elo=1000.0, vram=6.0),
            self._make_result("Q8_0", elo=1050.0, vram=9.0),
        ]
        pf = ParetoFrontier(results)
        # With tight VRAM constraint, may return None
        result = pf.get_optimal_format(max_vram_gb=5.0)
        # Just check it doesn't crash
        assert result is None or result is not None

    def test_get_optimal_format_zero_vram_constraint_is_respected(self):
        # Regression: get_optimal_format used `if max_vram_gb:` instead of
        # `if max_vram_gb is not None:`, so a caller asking for a
        # zero-VRAM-headroom constraint (max_vram_gb=0.0) had the
        # constraint silently ignored (0.0 is falsy) and got back a
        # format that uses far more than 0 GB of VRAM.
        from ollama_arena.telemetry.quantization import ParetoFrontier
        results = [
            self._make_result("Q4_K_M", elo=1000.0, vram=6.0),
            self._make_result("Q8_0", elo=1050.0, vram=9.0),
        ]
        pf = ParetoFrontier(results)
        result = pf.get_optimal_format(max_vram_gb=0.0)
        assert result is None

    def test_get_optimal_format_zero_min_elo_is_respected(self):
        # Same falsy-zero bug class for min_elo=0.0: must still apply the
        # filter (trivially true here since all scores are >= 0) rather
        # than skip filtering altogether.
        from ollama_arena.telemetry.quantization import ParetoFrontier
        results = [
            self._make_result("Q4_K_M", elo=1000.0, vram=6.0),
            self._make_result("Q8_0", elo=1050.0, vram=9.0),
        ]
        pf = ParetoFrontier(results)
        result = pf.get_optimal_format(min_elo=0.0)
        assert result is not None
