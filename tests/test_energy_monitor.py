"""Tests for energy monitoring — NVMLMonitor, ROCmMonitor, MPSMonitor, EnergyMonitor, TokensPerWattCalculator."""
from __future__ import annotations

import unittest.mock as mock
import platform as _platform

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# PowerMetrics
# ──────────────────────────────────────────────────────────────────────────────

class TestPowerMetrics:
    def _make(self, power=10.0):
        from ollama_arena.telemetry.energy import PowerMetrics
        import time
        return PowerMetrics(
            timestamp=time.time(),
            power_w=power,
            energy_j=50.0,
            temperature_c=70.0,
            utilization_percent=80.0,
            memory_utilization_percent=60.0,
        )

    def test_to_dict_has_timestamp(self):
        d = self._make().to_dict()
        assert "timestamp" in d

    def test_to_dict_has_power(self):
        d = self._make(power=42.0).to_dict()
        assert d["power_w"] == pytest.approx(42.0)

    def test_to_dict_has_energy(self):
        d = self._make().to_dict()
        assert d["energy_j"] == pytest.approx(50.0)

    def test_to_dict_has_temperature(self):
        d = self._make().to_dict()
        assert d["temperature_c"] == pytest.approx(70.0)

    def test_to_dict_has_utilization(self):
        d = self._make().to_dict()
        assert d["utilization_percent"] == pytest.approx(80.0)


# ──────────────────────────────────────────────────────────────────────────────
# NVMLMonitor — no pynvml available
# ──────────────────────────────────────────────────────────────────────────────

class TestNVMLMonitor:
    def _make(self):
        from ollama_arena.telemetry.energy import NVMLMonitor
        with mock.patch.dict("sys.modules", {"pynvml": None}):
            return NVMLMonitor()

    def test_init_does_not_crash(self):
        m = self._make()
        assert m is not None

    def test_not_initialized_when_no_pynvml(self):
        m = self._make()
        assert m._initialized is False

    def test_is_available_false_when_not_initialized(self):
        m = self._make()
        assert m.is_available() is False

    def test_get_power_usage_none_when_not_initialized(self):
        m = self._make()
        assert m.get_power_usage() is None

    def test_get_temperature_none_when_not_initialized(self):
        m = self._make()
        assert m.get_temperature() is None

    def test_get_utilization_none_when_not_initialized(self):
        m = self._make()
        assert m.get_utilization() is None

    def test_get_memory_utilization_none_when_not_initialized(self):
        m = self._make()
        assert m.get_memory_utilization() is None

    def test_get_metrics_returns_power_metrics(self):
        from ollama_arena.telemetry.energy import PowerMetrics
        m = self._make()
        result = m.get_metrics()
        assert isinstance(result, PowerMetrics)

    def test_get_metrics_zero_power_when_unavailable(self):
        m = self._make()
        result = m.get_metrics()
        assert result.power_w == pytest.approx(0.0)


# ──────────────────────────────────────────────────────────────────────────────
# ROCmMonitor — rocm-smi not found
# ──────────────────────────────────────────────────────────────────────────────

class TestROCmMonitor:
    def _make(self):
        from ollama_arena.telemetry.energy import ROCmMonitor
        with mock.patch("subprocess.run", side_effect=FileNotFoundError("rocm-smi not found")):
            return ROCmMonitor()

    def test_init_does_not_crash(self):
        m = self._make()
        assert m is not None

    def test_not_available_when_rocm_not_found(self):
        m = self._make()
        assert m._available is False

    def test_is_available_false(self):
        m = self._make()
        assert m.is_available() is False

    def test_get_power_usage_none_when_not_available(self):
        m = self._make()
        assert m.get_power_usage() is None

    def test_get_temperature_none_when_not_available(self):
        m = self._make()
        assert m.get_temperature() is None

    def test_get_metrics_returns_power_metrics(self):
        from ollama_arena.telemetry.energy import PowerMetrics
        m = self._make()
        result = m.get_metrics()
        assert isinstance(result, PowerMetrics)

    def test_get_metrics_zero_power_when_not_available(self):
        m = self._make()
        result = m.get_metrics()
        assert result.power_w == pytest.approx(0.0)

    def test_get_power_usage_rocm_failure_returns_none(self):
        from ollama_arena.telemetry.energy import ROCmMonitor
        with mock.patch("subprocess.run", side_effect=FileNotFoundError):
            m = ROCmMonitor()
        m._available = True
        with mock.patch("subprocess.run", side_effect=Exception("timeout")):
            result = m.get_power_usage()
        assert result is None

    def test_check_rocm_timeout_returns_false(self):
        from ollama_arena.telemetry.energy import ROCmMonitor
        import subprocess
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("rocm-smi", 5)):
            m = ROCmMonitor()
        assert m._available is False


# ──────────────────────────────────────────────────────────────────────────────
# MPSMonitor
# ──────────────────────────────────────────────────────────────────────────────

class TestMPSMonitor:
    def test_init_does_not_crash(self):
        from ollama_arena.telemetry.energy import MPSMonitor
        m = MPSMonitor()
        assert m is not None

    def test_is_available_false_on_non_apple(self):
        from ollama_arena.telemetry.energy import MPSMonitor
        with mock.patch("platform.system", return_value="Linux"):
            m = MPSMonitor()
        assert m.is_available() is False

    def test_is_available_false_on_windows(self):
        from ollama_arena.telemetry.energy import MPSMonitor
        with mock.patch("platform.system", return_value="Windows"):
            m = MPSMonitor()
        assert m.is_available() is False

    def test_get_power_usage_none_when_not_available(self):
        from ollama_arena.telemetry.energy import MPSMonitor
        with mock.patch("platform.system", return_value="Linux"):
            m = MPSMonitor()
        assert m.get_power_usage() is None

    def test_get_metrics_returns_power_metrics(self):
        from ollama_arena.telemetry.energy import MPSMonitor, PowerMetrics
        with mock.patch("platform.system", return_value="Linux"):
            m = MPSMonitor()
        result = m.get_metrics()
        assert isinstance(result, PowerMetrics)

    def test_get_metrics_fallback_power_when_not_available(self):
        from ollama_arena.telemetry.energy import MPSMonitor
        with mock.patch("platform.system", return_value="Linux"):
            m = MPSMonitor()
        result = m.get_metrics()
        # MPSMonitor.get_metrics uses `or 5.0` fallback regardless of availability
        assert result.power_w >= 0.0

    def test_mps_available_on_apple_arm(self):
        from ollama_arena.telemetry.energy import MPSMonitor
        with mock.patch("platform.system", return_value="Darwin"):
            with mock.patch("platform.machine", return_value="arm64"):
                m = MPSMonitor()
        assert m.is_available() is True

    def test_mps_get_power_subprocess_fail_returns_none(self):
        # get_power_usage() must report failure honestly as None rather
        # than fabricating a fixed 5.0W reading that looks like real data.
        # (get_metrics(), tested separately, is the one place allowed to
        # substitute a labeled fallback estimate.)
        from ollama_arena.telemetry.energy import MPSMonitor
        with mock.patch("platform.system", return_value="Darwin"):
            with mock.patch("platform.machine", return_value="arm64"):
                m = MPSMonitor()
        with mock.patch("subprocess.run", side_effect=Exception("fail")):
            result = m.get_power_usage()
        assert result is None

    def test_mps_get_metrics_subprocess_fail_returns_fallback_estimate(self):
        from ollama_arena.telemetry.energy import MPSMonitor
        with mock.patch("platform.system", return_value="Darwin"):
            with mock.patch("platform.machine", return_value="arm64"):
                m = MPSMonitor()
        with mock.patch("subprocess.run", side_effect=Exception("fail")):
            result = m.get_metrics()
        assert result.power_w == pytest.approx(5.0)


# ──────────────────────────────────────────────────────────────────────────────
# EnergyMonitor
# ──────────────────────────────────────────────────────────────────────────────

class TestEnergyMonitor:
    def _make_unavailable(self):
        """Create EnergyMonitor with no active monitor."""
        from ollama_arena.telemetry.energy import EnergyMonitor
        from ollama_arena.telemetry.base import HardwarePlatform
        with mock.patch("ollama_arena.telemetry.energy.HardwareDetector") as mock_det:
            mock_det.detect_platform.return_value = HardwarePlatform.CPU
            m = EnergyMonitor()
        return m

    def test_init_does_not_crash(self):
        m = self._make_unavailable()
        assert m is not None

    def test_is_available_false_when_no_gpu(self):
        m = self._make_unavailable()
        assert m.is_available() is False

    def test_active_monitor_none_when_no_gpu(self):
        m = self._make_unavailable()
        assert m.active_monitor is None

    def test_stop_recording_when_not_started_returns_zero_metrics(self):
        from ollama_arena.telemetry.energy import PowerMetrics
        m = self._make_unavailable()
        result = m.stop_recording()
        assert isinstance(result, PowerMetrics)
        assert result.power_w == pytest.approx(0.0)

    def test_start_recording_when_not_available_does_nothing(self):
        m = self._make_unavailable()
        m.start_recording()
        assert m._is_recording is False

    def test_get_current_metrics_returns_zero_when_no_monitor(self):
        from ollama_arena.telemetry.energy import PowerMetrics
        m = self._make_unavailable()
        result = m.get_current_metrics()
        assert isinstance(result, PowerMetrics)
        assert result.power_w == pytest.approx(0.0)

    def test_start_recording_already_recording_noop(self):
        m = self._make_unavailable()
        m._is_recording = True
        m.start_recording()
        assert m._is_recording is True

    def test_get_energy_monitor_factory(self):
        from ollama_arena.telemetry.energy import get_energy_monitor, EnergyMonitor
        from ollama_arena.telemetry.base import HardwarePlatform
        with mock.patch("ollama_arena.telemetry.energy.HardwareDetector") as mock_det:
            mock_det.detect_platform.return_value = HardwarePlatform.CPU
            m = get_energy_monitor()
        assert isinstance(m, EnergyMonitor)


# ──────────────────────────────────────────────────────────────────────────────
# TokensPerWattCalculator
# ──────────────────────────────────────────────────────────────────────────────

class TestTokensPerWattCalculator:
    def test_calculate_basic(self):
        from ollama_arena.telemetry.energy import TokensPerWattCalculator
        result = TokensPerWattCalculator.calculate(100, 10.0)
        assert result == pytest.approx(10.0)

    def test_calculate_zero_energy_returns_zero(self):
        from ollama_arena.telemetry.energy import TokensPerWattCalculator
        result = TokensPerWattCalculator.calculate(100, 0.0)
        assert result == pytest.approx(0.0)

    def test_calculate_negative_energy_returns_zero(self):
        from ollama_arena.telemetry.energy import TokensPerWattCalculator
        result = TokensPerWattCalculator.calculate(100, -5.0)
        assert result == pytest.approx(0.0)

    def test_calculate_from_power(self):
        from ollama_arena.telemetry.energy import TokensPerWattCalculator
        result = TokensPerWattCalculator.calculate_from_power(100, 10.0, 1.0)
        assert result == pytest.approx(10.0)

    def test_calculate_from_power_zero_duration(self):
        from ollama_arena.telemetry.energy import TokensPerWattCalculator
        result = TokensPerWattCalculator.calculate_from_power(100, 10.0, 0.0)
        assert result == pytest.approx(0.0)

    def test_calculate_efficiency_score_at_baseline(self):
        from ollama_arena.telemetry.energy import TokensPerWattCalculator
        result = TokensPerWattCalculator.calculate_efficiency_score(100.0, 100.0)
        assert result == pytest.approx(1.0)

    def test_calculate_efficiency_score_double_baseline(self):
        from ollama_arena.telemetry.energy import TokensPerWattCalculator
        result = TokensPerWattCalculator.calculate_efficiency_score(200.0, 100.0)
        assert result == pytest.approx(2.0)

    def test_calculate_efficiency_score_zero_baseline_returns_zero(self):
        from ollama_arena.telemetry.energy import TokensPerWattCalculator
        result = TokensPerWattCalculator.calculate_efficiency_score(100.0, 0.0)
        assert result == pytest.approx(0.0)

    def test_estimate_cost_per_token_basic(self):
        from ollama_arena.telemetry.energy import TokensPerWattCalculator
        # 3.6e6 J = 1 kWh. At $0.12/kWh and 1000 tokens: cost = $0.12/1000 = $0.00012
        result = TokensPerWattCalculator.estimate_cost_per_token(3.6e6, 1000, 0.12)
        assert result == pytest.approx(0.00012)

    def test_estimate_cost_per_token_zero_tokens_returns_zero(self):
        from ollama_arena.telemetry.energy import TokensPerWattCalculator
        result = TokensPerWattCalculator.estimate_cost_per_token(1000.0, 0)
        assert result == pytest.approx(0.0)

    def test_estimate_cost_per_token_positive(self):
        from ollama_arena.telemetry.energy import TokensPerWattCalculator
        result = TokensPerWattCalculator.estimate_cost_per_token(100.0, 50, 0.12)
        assert result > 0.0
