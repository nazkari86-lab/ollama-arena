"""Tests for telemetry monitors — PSUtilBandwidthMonitor, EnergyMonitor, BandwidthMonitor."""
from __future__ import annotations

import time
import unittest.mock as mock

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# PSUtilBandwidthMonitor
# ──────────────────────────────────────────────────────────────────────────────

class TestPSUtilBandwidthMonitor:
    def _make(self):
        from ollama_arena.telemetry.bandwidth import PSUtilBandwidthMonitor
        return PSUtilBandwidthMonitor()

    def test_check_psutil_returns_bool(self):
        m = self._make()
        result = m._check_psutil()
        assert isinstance(result, bool)

    def test_is_available_returns_bool(self):
        m = self._make()
        assert isinstance(m.is_available(), bool)

    def test_stop_monitoring_is_noop(self):
        m = self._make()
        m.stop_monitoring()  # Must not raise

    def test_start_monitoring_unavailable_returns_false(self):
        m = self._make()
        m._available = False
        result = m.start_monitoring()
        assert result is False

    def test_get_metrics_unavailable_returns_none(self):
        m = self._make()
        m._available = False
        result = m.get_metrics()
        assert result is None

    def test_start_monitoring_with_mock_psutil(self):
        m = self._make()
        m._available = True
        fake_mem = mock.MagicMock()
        fake_mem.used = 4 * (1024**3)  # 4 GB
        with mock.patch("psutil.virtual_memory", return_value=fake_mem):
            result = m.start_monitoring()
        assert result is True
        assert m._previous_used == 4.0
        assert m._previous_time > 0

    def test_get_metrics_with_mock_psutil(self):
        from ollama_arena.telemetry.bandwidth import BandwidthMetrics
        m = self._make()
        m._available = True
        m._previous_used = 4.0
        m._previous_time = time.time() - 1.0  # 1 second ago

        fake_mem = mock.MagicMock()
        fake_mem.used = 4.5 * (1024**3)
        fake_mem.total = 16 * (1024**3)
        fake_mem.percent = 28.0

        with mock.patch("psutil.virtual_memory", return_value=fake_mem):
            result = m.get_metrics()

        assert isinstance(result, BandwidthMetrics)
        assert result.memory_used_gb == pytest.approx(4.5, rel=0.01)
        assert result.memory_total_gb == pytest.approx(16.0, rel=0.01)
        assert result.memory_percent == 28.0

    def test_get_metrics_psutil_exception_returns_none(self):
        m = self._make()
        m._available = True
        with mock.patch("psutil.virtual_memory", side_effect=RuntimeError("fail")):
            result = m.get_metrics()
        assert result is None

    def test_start_monitoring_psutil_exception_returns_false(self):
        m = self._make()
        m._available = True
        with mock.patch("psutil.virtual_memory", side_effect=RuntimeError("fail")):
            result = m.start_monitoring()
        assert result is False


# ──────────────────────────────────────────────────────────────────────────────
# BandwidthProfiler — top-level orchestrator
# ──────────────────────────────────────────────────────────────────────────────

class TestBandwidthProfiler:
    def test_default_construction_does_not_crash(self):
        # Regression: BandwidthProfiler.__init__ took a `platform` parameter
        # that shadowed the module-level `import platform`, so
        # `platform.system()` crashed with AttributeError on every real
        # instantiation (verified on this machine: 'NoneType' object has
        # no attribute 'system' when hw_platform defaults to None).
        from ollama_arena.telemetry.bandwidth import BandwidthProfiler
        profiler = BandwidthProfiler()
        assert profiler is not None
        assert isinstance(profiler.is_available(), bool)

    def test_factory_does_not_crash(self):
        from ollama_arena.telemetry.bandwidth import get_bandwidth_profiler
        profiler = get_bandwidth_profiler()
        assert profiler is not None

    def test_explicit_hw_platform_construction_does_not_crash(self):
        from ollama_arena.telemetry.bandwidth import BandwidthProfiler
        from ollama_arena.telemetry.base import HardwarePlatform
        profiler = BandwidthProfiler(HardwarePlatform.NVIDIA)
        assert profiler.platform == HardwarePlatform.NVIDIA

    def test_linux_only_monitors_none_on_non_linux(self):
        import platform as platform_module
        from ollama_arena.telemetry.bandwidth import BandwidthProfiler
        profiler = BandwidthProfiler()
        if platform_module.system() != "Linux":
            assert profiler.ebpf_monitor is None
            assert profiler.proc_monitor is None


# ──────────────────────────────────────────────────────────────────────────────
# EBPFBandwidthMonitor (Linux-only, available=False on macOS)
# ──────────────────────────────────────────────────────────────────────────────

class TestEBPFBandwidthMonitor:
    def _make(self):
        from ollama_arena.telemetry.bandwidth import EBPFBandwidthMonitor
        return EBPFBandwidthMonitor()

    def test_init_does_not_crash(self):
        m = self._make()
        assert m is not None

    def test_is_available_returns_bool(self):
        m = self._make()
        assert isinstance(m.is_available(), bool)

    def test_start_monitoring_unavailable_returns_false(self):
        m = self._make()
        m._available = False
        result = m.start_monitoring()
        assert result is False

    def test_get_bandwidth_unavailable_returns_none(self):
        m = self._make()
        m._available = False
        assert m.get_bandwidth() is None

    def test_stop_monitoring_is_noop(self):
        m = self._make()
        m.stop_monitoring()  # Must not raise


# ──────────────────────────────────────────────────────────────────────────────
# ProcMeminfoMonitor (Linux-only, available=False on macOS)
# ──────────────────────────────────────────────────────────────────────────────

class TestProcMeminfoMonitor:
    def _make(self):
        from ollama_arena.telemetry.bandwidth import ProcMeminfoMonitor
        return ProcMeminfoMonitor()

    def test_init_does_not_crash(self):
        m = self._make()
        assert m is not None

    def test_is_available_returns_bool(self):
        m = self._make()
        assert isinstance(m.is_available(), bool)

    def test_start_monitoring_unavailable_returns_false(self):
        m = self._make()
        m._available = False
        result = m.start_monitoring()
        assert result is False

    def test_get_metrics_unavailable_returns_none(self):
        m = self._make()
        m._available = False
        assert m.get_metrics() is None

    def test_stop_monitoring_is_noop(self):
        m = self._make()
        m.stop_monitoring()  # Must not raise


# ──────────────────────────────────────────────────────────────────────────────
# EnergyMonitor
# ──────────────────────────────────────────────────────────────────────────────

class TestEnergyMonitor:
    def _make(self):
        from ollama_arena.telemetry.energy import EnergyMonitor
        return EnergyMonitor()

    def test_init_does_not_crash(self):
        m = self._make()
        assert m is not None

    def test_is_available_returns_bool(self):
        m = self._make()
        assert isinstance(m.is_available(), bool)

    def test_stop_recording_when_not_recording_returns_power_metrics(self):
        from ollama_arena.telemetry.energy import PowerMetrics
        m = self._make()
        result = m.stop_recording()
        assert isinstance(result, PowerMetrics)
        assert result.power_w == 0.0

    def test_stop_recording_when_not_recording_has_timestamp(self):
        from ollama_arena.telemetry.energy import PowerMetrics
        m = self._make()
        before = time.time()
        result = m.stop_recording()
        after = time.time()
        assert before <= result.timestamp <= after

    def test_start_recording_no_monitor_is_noop(self):
        m = self._make()
        m.active_monitor = None  # Force no monitor
        m.start_recording()  # Must not raise
        assert m._is_recording is False

    def test_start_recording_already_recording_is_noop(self):
        m = self._make()
        m._is_recording = True
        m.start_recording()  # Must not raise (guard: already recording)

    def test_device_index_stored(self):
        from ollama_arena.telemetry.energy import EnergyMonitor
        m = EnergyMonitor(device_index=2)
        assert m.device_index == 2

    def test_is_available_false_when_no_active_monitor(self):
        m = self._make()
        m.active_monitor = None
        assert m.is_available() is False

    def test_platform_attribute_is_hardware_platform(self):
        from ollama_arena.telemetry.base import HardwarePlatform
        m = self._make()
        assert isinstance(m.platform, HardwarePlatform)

    def test_power_metrics_to_dict(self):
        from ollama_arena.telemetry.energy import PowerMetrics
        m = self._make()
        result = m.stop_recording()
        d = result.to_dict()
        for key in ["timestamp", "power_w", "energy_j", "temperature_c"]:
            assert key in d


# ──────────────────────────────────────────────────────────────────────────────
# NVMLMonitor — without actual GPU
# ──────────────────────────────────────────────────────────────────────────────

class TestNVMLMonitorNoGPU:
    def _make(self):
        from ollama_arena.telemetry.energy import NVMLMonitor
        return NVMLMonitor()

    def test_init_does_not_crash(self):
        m = self._make()
        assert m is not None

    def test_is_available_returns_bool(self):
        m = self._make()
        assert isinstance(m.is_available(), bool)

    def test_get_power_usage_returns_none_when_unavailable(self):
        m = self._make()
        m._initialized = False
        result = m.get_power_usage()
        assert result is None

    def test_get_metrics_runs_when_unavailable(self):
        from ollama_arena.telemetry.energy import PowerMetrics
        m = self._make()
        m._initialized = False
        result = m.get_metrics()
        assert isinstance(result, PowerMetrics)


# ──────────────────────────────────────────────────────────────────────────────
# ROCmMonitor — without actual GPU
# ──────────────────────────────────────────────────────────────────────────────

class TestROCmMonitorNoGPU:
    def _make(self):
        from ollama_arena.telemetry.energy import ROCmMonitor
        return ROCmMonitor()

    def test_init_does_not_crash(self):
        m = self._make()
        assert m is not None

    def test_is_available_returns_bool(self):
        m = self._make()
        assert isinstance(m.is_available(), bool)

    def test_get_power_usage_returns_none_when_unavailable(self):
        m = self._make()
        if not m.is_available():
            result = m.get_power_usage()
            assert result is None

    def test_check_rocm_does_not_crash_on_permission_error(self):
        # Regression: _check_rocm only caught (FileNotFoundError,
        # TimeoutExpired). A PermissionError (e.g. a stale non-executable
        # rocm-smi stub on PATH) is also an OSError but is a different
        # subclass, and used to propagate uncaught out of __init__.
        from ollama_arena.telemetry.energy import ROCmMonitor
        with mock.patch("subprocess.run", side_effect=PermissionError("denied")):
            m = ROCmMonitor()  # Must not raise
        assert m.is_available() is False


# ──────────────────────────────────────────────────────────────────────────────
# MPSMonitor — without Apple GPU
# ──────────────────────────────────────────────────────────────────────────────

class TestMPSMonitorNoGPU:
    def _make(self):
        from ollama_arena.telemetry.energy import MPSMonitor
        return MPSMonitor()

    def test_init_does_not_crash(self):
        m = self._make()
        assert m is not None

    def test_is_available_returns_bool(self):
        m = self._make()
        assert isinstance(m.is_available(), bool)

    def test_get_power_usage_no_crash(self):
        m = self._make()
        result = m.get_power_usage()
        assert result is None or isinstance(result, float)

    def test_get_power_usage_returns_none_on_subprocess_failure(self):
        # Regression: get_power_usage() used to swallow the (extremely
        # common, since powermetrics needs sudo/a TTY) failure and return
        # a hardcoded 5.0, disguising "we couldn't measure" as a real
        # reading. It must now report None so callers can tell the
        # difference between "measured 5W" and "unknown".
        m = self._make()
        m._available = True
        with mock.patch("subprocess.run", side_effect=OSError("no tty")):
            result = m.get_power_usage()
        assert result is None

    def test_get_metrics_falls_back_to_labeled_estimate_on_failure(self):
        # get_metrics() is the one place allowed to substitute an estimate;
        # it should still produce a usable PowerMetrics even though the
        # underlying measurement failed.
        from ollama_arena.telemetry.energy import PowerMetrics
        m = self._make()
        m._available = True
        with mock.patch("subprocess.run", side_effect=OSError("no tty")):
            result = m.get_metrics()
        assert isinstance(result, PowerMetrics)
        assert result.power_w == 5.0
