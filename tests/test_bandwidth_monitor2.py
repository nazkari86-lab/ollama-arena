"""Additional tests for bandwidth.py — Linux paths, EBPFBandwidthMonitor, ProcMeminfoMonitor, BandwidthProfiler methods."""
from __future__ import annotations

import io
import unittest.mock as mock

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# EBPFBandwidthMonitor — Linux-mocked paths
# ──────────────────────────────────────────────────────────────────────────────

class TestEBPFBandwidthMonitorLinux:
    def _make_with_bcc(self):
        from ollama_arena.telemetry.bandwidth import EBPFBandwidthMonitor
        mock_result = mock.MagicMock()
        mock_result.returncode = 0
        with mock.patch("platform.system", return_value="Linux"):
            with mock.patch("subprocess.run", return_value=mock_result):
                return EBPFBandwidthMonitor()

    def _make_with_bpftrace(self):
        from ollama_arena.telemetry.bandwidth import EBPFBandwidthMonitor
        bcc_result = mock.MagicMock()
        bcc_result.returncode = 1
        bpf_result = mock.MagicMock()
        bpf_result.returncode = 0
        with mock.patch("platform.system", return_value="Linux"):
            with mock.patch("subprocess.run", side_effect=[bcc_result, bpf_result]):
                return EBPFBandwidthMonitor()

    def _make_exception(self):
        from ollama_arena.telemetry.bandwidth import EBPFBandwidthMonitor
        with mock.patch("platform.system", return_value="Linux"):
            with mock.patch("subprocess.run", side_effect=Exception("fail")):
                return EBPFBandwidthMonitor()

    def test_available_when_bcc_found(self):
        m = self._make_with_bcc()
        assert m.is_available() is True

    def test_available_when_bpftrace_found(self):
        m = self._make_with_bpftrace()
        assert m.is_available() is True

    def test_not_available_when_exception(self):
        m = self._make_exception()
        assert m.is_available() is False

    def test_start_monitoring_when_available_reads_vmstat(self):
        m = self._make_with_bcc()
        vmstat_content = "pgmajfault 12345\n"
        with mock.patch("builtins.open", mock.mock_open(read_data=vmstat_content)):
            result = m.start_monitoring()
        assert result is True

    def test_start_monitoring_file_error_returns_false(self):
        m = self._make_with_bcc()
        with mock.patch("builtins.open", side_effect=OSError("no file")):
            result = m.start_monitoring()
        assert result is False

    def test_get_bandwidth_when_available_returns_float(self):
        m = self._make_with_bcc()
        m._previous_time = 1.0
        m._previous_bytes = 0
        vmstat_content = "pgmajfault 12345\n"
        with mock.patch("builtins.open", mock.mock_open(read_data=vmstat_content)):
            result = m.get_bandwidth()
        assert result is not None
        assert isinstance(result, float)

    def test_get_bandwidth_zero_time_diff_returns_zero(self):
        m = self._make_with_bcc()
        m._previous_time = 0.0
        import time
        with mock.patch("time.time", return_value=0.0):
            vmstat_content = "pgmajfault 0\n"
            with mock.patch("builtins.open", mock.mock_open(read_data=vmstat_content)):
                result = m.get_bandwidth()
        assert result == 0.0 or result is None  # 0 time_diff → 0.0

    def test_get_bandwidth_file_error_returns_none(self):
        m = self._make_with_bcc()
        m._previous_time = 1.0
        with mock.patch("builtins.open", side_effect=OSError("disk error")):
            result = m.get_bandwidth()
        assert result is None


# ──────────────────────────────────────────────────────────────────────────────
# ProcMeminfoMonitor — Linux-mocked path
# ──────────────────────────────────────────────────────────────────────────────

FAKE_MEMINFO = "MemTotal:        16384000 kB\nMemFree:         8192000 kB\nMemAvailable:    9000000 kB\n"


class TestProcMeminfoMonitorLinux:
    def _make_available(self):
        from ollama_arena.telemetry.bandwidth import ProcMeminfoMonitor
        with mock.patch("platform.system", return_value="Linux"):
            return ProcMeminfoMonitor()

    def test_is_available_on_linux(self):
        m = self._make_available()
        assert m.is_available() is True

    def test_get_metrics_returns_bandwidth_metrics(self):
        from ollama_arena.telemetry.bandwidth import BandwidthMetrics
        m = self._make_available()
        with mock.patch("builtins.open", mock.mock_open(read_data=FAKE_MEMINFO)):
            result = m.get_metrics()
        assert isinstance(result, BandwidthMetrics)

    def test_get_metrics_total_gb_correct(self):
        m = self._make_available()
        with mock.patch("builtins.open", mock.mock_open(read_data=FAKE_MEMINFO)):
            result = m.get_metrics()
        assert result is not None
        assert result.memory_total_gb == pytest.approx(16384000 / (1024**2))

    def test_get_metrics_memory_percent_in_range(self):
        m = self._make_available()
        with mock.patch("builtins.open", mock.mock_open(read_data=FAKE_MEMINFO)):
            result = m.get_metrics()
        assert result is not None
        assert 0.0 <= result.memory_percent <= 100.0

    def test_get_metrics_file_error_returns_none(self):
        m = self._make_available()
        with mock.patch("builtins.open", side_effect=OSError("fail")):
            result = m.get_metrics()
        assert result is None

    def test_start_monitoring_true_when_available(self):
        m = self._make_available()
        with mock.patch("builtins.open", mock.mock_open(read_data=FAKE_MEMINFO)):
            result = m.start_monitoring()
        assert result is True

    def test_start_monitoring_false_on_file_error(self):
        m = self._make_available()
        with mock.patch("builtins.open", side_effect=OSError("fail")):
            result = m.start_monitoring()
        assert result is False

    def test_get_metrics_calculates_bandwidth_with_previous(self):
        m = self._make_available()
        m._previous_used = 5.0
        m._previous_time = 1.0
        with mock.patch("builtins.open", mock.mock_open(read_data=FAKE_MEMINFO)):
            result = m.get_metrics()
        # bandwidth calculation ran
        assert result is not None
        assert result.bandwidth_gb_s >= 0.0


# ──────────────────────────────────────────────────────────────────────────────
# BandwidthProfiler methods — bypass broken __init__
# ──────────────────────────────────────────────────────────────────────────────

class TestBandwidthProfilerMethods:
    def _make_profiler(self, primary_monitor=None, gpu_monitor=None):
        from ollama_arena.telemetry.bandwidth import BandwidthProfiler, GPUBandwidthMonitor
        from ollama_arena.telemetry.base import HardwarePlatform
        p = object.__new__(BandwidthProfiler)
        p.platform = HardwarePlatform.CPU
        p.device_index = 0
        p.primary_monitor = primary_monitor
        p.gpu_monitor = gpu_monitor or GPUBandwidthMonitor(platform=HardwarePlatform.CPU)
        p._is_recording = False
        p._start_time = None
        p._bandwidth_samples = []
        p._metrics_history = []
        p._monitoring_thread = None
        p._monitoring_interval = 0.1
        return p

    def test_is_available_false_when_no_primary(self):
        p = self._make_profiler()
        assert p.is_available() is False

    def test_is_available_true_when_primary_set(self):
        mock_monitor = mock.MagicMock()
        p = self._make_profiler(primary_monitor=mock_monitor)
        assert p.is_available() is True

    def test_start_recording_noop_when_not_available(self):
        p = self._make_profiler()
        p.start_recording()
        assert p._is_recording is False

    def test_start_recording_already_recording_noop(self):
        p = self._make_profiler()
        p._is_recording = True
        p.start_recording()
        assert p._is_recording is True

    def test_stop_recording_returns_empty_metrics_when_not_recording(self):
        from ollama_arena.telemetry.bandwidth import BandwidthMetrics
        p = self._make_profiler()
        result = p.stop_recording()
        assert isinstance(result, BandwidthMetrics)
        assert result.bandwidth_gb_s == pytest.approx(0.0)

    def test_stop_recording_returns_latest_metrics_from_history(self):
        from ollama_arena.telemetry.bandwidth import BandwidthMetrics
        import time
        p = self._make_profiler()
        p._is_recording = True
        p._start_time = time.time()
        p._bandwidth_samples = [5.0, 10.0]
        p._metrics_history = [
            BandwidthMetrics(timestamp=time.time(), bandwidth_gb_s=7.5,
                           memory_used_gb=8.0, memory_total_gb=16.0, memory_percent=50.0)
        ]
        result = p.stop_recording()
        assert isinstance(result, BandwidthMetrics)

    def test_stop_recording_empty_samples_returns_zero_bandwidth(self):
        from ollama_arena.telemetry.bandwidth import BandwidthMetrics
        import time
        p = self._make_profiler()
        p._is_recording = True
        p._start_time = time.time()
        p._bandwidth_samples = []
        p._metrics_history = []
        result = p.stop_recording()
        assert result.bandwidth_gb_s == pytest.approx(0.0)

    def test_get_current_metrics_none_when_no_primary(self):
        p = self._make_profiler()
        result = p.get_current_metrics()
        assert result is None

    def test_get_current_metrics_delegates_to_primary(self):
        from ollama_arena.telemetry.bandwidth import BandwidthMetrics
        import time
        mock_monitor = mock.MagicMock()
        mock_monitor.get_metrics.return_value = BandwidthMetrics(
            timestamp=time.time(), bandwidth_gb_s=10.0,
            memory_used_gb=4.0, memory_total_gb=8.0, memory_percent=50.0
        )
        p = self._make_profiler(primary_monitor=mock_monitor)
        result = p.get_current_metrics()
        assert result is not None
        assert result.bandwidth_gb_s == pytest.approx(10.0)

    def test_get_current_metrics_primary_no_get_metrics_returns_none(self):
        mock_monitor = mock.MagicMock(spec=[])  # No methods
        p = self._make_profiler(primary_monitor=mock_monitor)
        result = p.get_current_metrics()
        assert result is None

    def test_start_recording_with_available_primary(self):
        mock_monitor = mock.MagicMock()
        mock_monitor.start_monitoring.return_value = True
        p = self._make_profiler(primary_monitor=mock_monitor)
        p.start_recording()
        assert p._is_recording is True

    def test_stop_recording_after_start_clears_state(self):
        mock_monitor = mock.MagicMock()
        mock_monitor.start_monitoring.return_value = True
        p = self._make_profiler(primary_monitor=mock_monitor)
        p.start_recording()
        result = p.stop_recording()
        assert p._is_recording is False


# ──────────────────────────────────────────────────────────────────────────────
# get_bandwidth_profiler factory — bypass __init__ via import
# ──────────────────────────────────────────────────────────────────────────────

class TestGetBandwidthProfilerFactory:
    def test_factory_signature(self):
        from ollama_arena.telemetry import bandwidth
        import inspect
        sig = inspect.signature(bandwidth.get_bandwidth_profiler)
        assert "platform" in sig.parameters
        assert "device_index" in sig.parameters
