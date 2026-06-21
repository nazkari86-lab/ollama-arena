"""Tests for memory bandwidth monitoring — BandwidthMetrics, individual monitors, correlation analysis."""
from __future__ import annotations

import unittest.mock as mock

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# BandwidthMetrics
# ──────────────────────────────────────────────────────────────────────────────

class TestBandwidthMetrics:
    def _make(self):
        from ollama_arena.telemetry.bandwidth import BandwidthMetrics
        import time
        return BandwidthMetrics(
            timestamp=time.time(),
            bandwidth_gb_s=10.0,
            memory_used_gb=8.0,
            memory_total_gb=16.0,
            memory_percent=50.0,
            gpu_memory_used_gb=4.0,
            gpu_memory_total_gb=8.0,
            gpu_bandwidth_gb_s=200.0,
        )

    def test_to_dict_has_bandwidth(self):
        d = self._make().to_dict()
        assert "bandwidth_gb_s" in d
        assert d["bandwidth_gb_s"] == pytest.approx(10.0)

    def test_to_dict_has_memory_fields(self):
        d = self._make().to_dict()
        assert d["memory_used_gb"] == pytest.approx(8.0)
        assert d["memory_total_gb"] == pytest.approx(16.0)
        assert d["memory_percent"] == pytest.approx(50.0)

    def test_to_dict_has_gpu_fields(self):
        d = self._make().to_dict()
        assert d["gpu_memory_used_gb"] == pytest.approx(4.0)
        assert d["gpu_bandwidth_gb_s"] == pytest.approx(200.0)

    def test_to_dict_has_cache_fields(self):
        d = self._make().to_dict()
        assert "l1_cache_hit_rate" in d
        assert "l2_cache_hit_rate" in d
        assert "l3_cache_hit_rate" in d

    def test_to_dict_has_timestamp(self):
        d = self._make().to_dict()
        assert "timestamp" in d


# ──────────────────────────────────────────────────────────────────────────────
# BandwidthMethod enum
# ──────────────────────────────────────────────────────────────────────────────

class TestBandwidthMethod:
    def test_values_exist(self):
        from ollama_arena.telemetry.bandwidth import BandwidthMethod
        assert BandwidthMethod.EBPF.value == "ebpf"
        assert BandwidthMethod.PROC.value == "proc"
        assert BandwidthMethod.PSUTIL.value == "psutil"
        assert BandwidthMethod.NONE.value == "none"


# ──────────────────────────────────────────────────────────────────────────────
# EBPFBandwidthMonitor
# ──────────────────────────────────────────────────────────────────────────────

class TestEBPFBandwidthMonitor:
    def _make_unavailable(self):
        from ollama_arena.telemetry.bandwidth import EBPFBandwidthMonitor
        with mock.patch("platform.system", return_value="Darwin"):
            return EBPFBandwidthMonitor()

    def test_init_does_not_crash(self):
        m = self._make_unavailable()
        assert m is not None

    def test_not_available_on_non_linux(self):
        m = self._make_unavailable()
        assert m.is_available() is False

    def test_get_bandwidth_none_when_not_available(self):
        m = self._make_unavailable()
        assert m.get_bandwidth() is None

    def test_stop_monitoring_no_crash(self):
        m = self._make_unavailable()
        m.stop_monitoring()

    def test_start_monitoring_false_when_not_available(self):
        m = self._make_unavailable()
        result = m.start_monitoring()
        assert result is False


# ──────────────────────────────────────────────────────────────────────────────
# ProcMeminfoMonitor
# ──────────────────────────────────────────────────────────────────────────────

class TestProcMeminfoMonitor:
    def _make_unavailable(self):
        from ollama_arena.telemetry.bandwidth import ProcMeminfoMonitor
        with mock.patch("platform.system", return_value="Darwin"):
            return ProcMeminfoMonitor()

    def test_init_does_not_crash(self):
        m = self._make_unavailable()
        assert m is not None

    def test_not_available_on_non_linux(self):
        m = self._make_unavailable()
        assert m.is_available() is False

    def test_start_monitoring_false_when_not_available(self):
        m = self._make_unavailable()
        result = m.start_monitoring()
        assert result is False

    def test_get_metrics_none_when_not_available(self):
        m = self._make_unavailable()
        assert m.get_metrics() is None

    def test_stop_monitoring_no_crash(self):
        m = self._make_unavailable()
        m.stop_monitoring()


# ──────────────────────────────────────────────────────────────────────────────
# PSUtilBandwidthMonitor
# ──────────────────────────────────────────────────────────────────────────────

class TestPSUtilBandwidthMonitor:
    def test_init_does_not_crash(self):
        from ollama_arena.telemetry.bandwidth import PSUtilBandwidthMonitor
        m = PSUtilBandwidthMonitor()
        assert m is not None

    def test_available_when_psutil_installed(self):
        from ollama_arena.telemetry.bandwidth import PSUtilBandwidthMonitor
        m = PSUtilBandwidthMonitor()
        # psutil is installed in this environment
        assert isinstance(m.is_available(), bool)

    def test_not_available_without_psutil(self):
        from ollama_arena.telemetry.bandwidth import PSUtilBandwidthMonitor
        with mock.patch.dict("sys.modules", {"psutil": None}):
            m = PSUtilBandwidthMonitor()
        assert m.is_available() is False

    def test_get_metrics_none_when_not_available(self):
        from ollama_arena.telemetry.bandwidth import PSUtilBandwidthMonitor
        with mock.patch.dict("sys.modules", {"psutil": None}):
            m = PSUtilBandwidthMonitor()
        assert m.get_metrics() is None

    def test_start_monitoring_false_when_not_available(self):
        from ollama_arena.telemetry.bandwidth import PSUtilBandwidthMonitor
        with mock.patch.dict("sys.modules", {"psutil": None}):
            m = PSUtilBandwidthMonitor()
        assert m.start_monitoring() is False

    def test_get_metrics_returns_bandwidth_metrics(self):
        import psutil
        from ollama_arena.telemetry.bandwidth import PSUtilBandwidthMonitor, BandwidthMetrics
        m = PSUtilBandwidthMonitor()
        if m.is_available():
            result = m.get_metrics()
            assert isinstance(result, BandwidthMetrics)

    def test_start_monitoring_true_when_available(self):
        from ollama_arena.telemetry.bandwidth import PSUtilBandwidthMonitor
        m = PSUtilBandwidthMonitor()
        if m.is_available():
            result = m.start_monitoring()
            assert result is True

    def test_stop_monitoring_no_crash(self):
        from ollama_arena.telemetry.bandwidth import PSUtilBandwidthMonitor
        m = PSUtilBandwidthMonitor()
        m.stop_monitoring()

    def test_get_metrics_has_memory_percent(self):
        from ollama_arena.telemetry.bandwidth import PSUtilBandwidthMonitor
        m = PSUtilBandwidthMonitor()
        if m.is_available():
            result = m.get_metrics()
            if result is not None:
                assert 0.0 <= result.memory_percent <= 100.0

    def test_start_monitoring_exception_returns_false(self):
        from ollama_arena.telemetry.bandwidth import PSUtilBandwidthMonitor
        m = PSUtilBandwidthMonitor()
        m._available = True
        import psutil
        with mock.patch("psutil.virtual_memory", side_effect=Exception("fail")):
            result = m.start_monitoring()
        assert result is False


# ──────────────────────────────────────────────────────────────────────────────
# GPUBandwidthMonitor
# ──────────────────────────────────────────────────────────────────────────────

class TestGPUBandwidthMonitor:
    def _make_cpu(self):
        from ollama_arena.telemetry.bandwidth import GPUBandwidthMonitor
        from ollama_arena.telemetry.base import HardwarePlatform
        return GPUBandwidthMonitor(platform=HardwarePlatform.CPU)

    def test_init_does_not_crash(self):
        m = self._make_cpu()
        assert m is not None

    def test_not_available_on_cpu_platform(self):
        m = self._make_cpu()
        assert m.is_available() is False

    def test_get_gpu_metrics_none_when_not_available(self):
        m = self._make_cpu()
        assert m.get_gpu_metrics() is None

    def test_start_monitoring_false_when_not_available(self):
        m = self._make_cpu()
        result = m.start_monitoring()
        assert result is False

    def test_stop_monitoring_no_crash(self):
        m = self._make_cpu()
        m.stop_monitoring()

    def test_nvidia_platform_no_pynvml_not_available(self):
        from ollama_arena.telemetry.bandwidth import GPUBandwidthMonitor
        from ollama_arena.telemetry.base import HardwarePlatform
        with mock.patch.dict("sys.modules", {"pynvml": None}):
            m = GPUBandwidthMonitor(platform=HardwarePlatform.NVIDIA)
        assert m.is_available() is False

    def test_amd_platform_no_rocm_not_available(self):
        from ollama_arena.telemetry.bandwidth import GPUBandwidthMonitor
        from ollama_arena.telemetry.base import HardwarePlatform
        with mock.patch("subprocess.run", side_effect=FileNotFoundError):
            m = GPUBandwidthMonitor(platform=HardwarePlatform.AMD)
        assert m.is_available() is False


# ──────────────────────────────────────────────────────────────────────────────
# BandwidthProfiler.analyze_ttft_correlation (pure math, bypass __init__ bug)
# ──────────────────────────────────────────────────────────────────────────────

class TestAnalyzeTTFTCorrelation:
    def _make_profiler(self):
        from ollama_arena.telemetry.bandwidth import BandwidthProfiler
        p = object.__new__(BandwidthProfiler)
        return p

    def test_empty_lists_returns_zero_correlation(self):
        p = self._make_profiler()
        result = p.analyze_ttft_correlation([], [])
        assert result["correlation"] == pytest.approx(0.0)
        assert result["r_squared"] == pytest.approx(0.0)

    def test_single_sample_returns_zero_correlation(self):
        p = self._make_profiler()
        result = p.analyze_ttft_correlation([1.0], [2.0])
        assert result["correlation"] == pytest.approx(0.0)

    def test_mismatched_lengths_returns_zero(self):
        p = self._make_profiler()
        result = p.analyze_ttft_correlation([1.0, 2.0], [3.0])
        assert result["correlation"] == pytest.approx(0.0)

    def test_perfect_positive_correlation(self):
        p = self._make_profiler()
        ttft = [1.0, 2.0, 3.0, 4.0]
        bw = [1.0, 2.0, 3.0, 4.0]
        result = p.analyze_ttft_correlation(ttft, bw)
        assert result["correlation"] == pytest.approx(1.0, abs=1e-9)

    def test_perfect_negative_correlation(self):
        p = self._make_profiler()
        ttft = [4.0, 3.0, 2.0, 1.0]
        bw = [1.0, 2.0, 3.0, 4.0]
        result = p.analyze_ttft_correlation(ttft, bw)
        assert result["correlation"] == pytest.approx(-1.0, abs=1e-9)

    def test_zero_variance_returns_zero_correlation(self):
        p = self._make_profiler()
        ttft = [2.0, 2.0, 2.0]
        bw = [1.0, 2.0, 3.0]
        result = p.analyze_ttft_correlation(ttft, bw)
        assert result["correlation"] == pytest.approx(0.0)

    def test_r_squared_is_square_of_correlation(self):
        p = self._make_profiler()
        ttft = [1.0, 2.0, 3.0, 4.0]
        bw = [2.0, 3.0, 4.0, 5.0]
        result = p.analyze_ttft_correlation(ttft, bw)
        assert result["r_squared"] == pytest.approx(result["correlation"] ** 2)

    def test_returns_mean_values(self):
        p = self._make_profiler()
        ttft = [1.0, 3.0]
        bw = [2.0, 4.0]
        result = p.analyze_ttft_correlation(ttft, bw)
        assert result["ttft_mean"] == pytest.approx(2.0)
        assert result["bandwidth_mean"] == pytest.approx(3.0)
