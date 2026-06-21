"""Tests for telemetry base module — HardwarePlatform, HardwareInfo, TelemetryRecord."""
from __future__ import annotations

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# HardwarePlatform
# ──────────────────────────────────────────────────────────────────────────────

class TestHardwarePlatform:
    def test_all_platforms_present(self):
        from ollama_arena.telemetry.base import HardwarePlatform
        values = {p.value for p in HardwarePlatform}
        assert "nvidia" in values
        assert "amd" in values
        assert "apple" in values
        assert "cpu" in values
        assert "unknown" in values

    def test_from_value(self):
        from ollama_arena.telemetry.base import HardwarePlatform
        assert HardwarePlatform("nvidia") == HardwarePlatform.NVIDIA

    def test_count(self):
        from ollama_arena.telemetry.base import HardwarePlatform
        assert len(list(HardwarePlatform)) == 5


# ──────────────────────────────────────────────────────────────────────────────
# HardwareInfo
# ──────────────────────────────────────────────────────────────────────────────

class TestHardwareInfo:
    def _make(self, **kw):
        from ollama_arena.telemetry.base import HardwareInfo, HardwarePlatform
        defaults = dict(platform=HardwarePlatform.CPU)
        defaults.update(kw)
        return HardwareInfo(**defaults)

    def test_basic_creation(self):
        hw = self._make()
        from ollama_arena.telemetry.base import HardwarePlatform
        assert hw.platform == HardwarePlatform.CPU

    def test_default_values(self):
        hw = self._make()
        assert hw.device_name == ""
        assert hw.total_memory_gb == 0.0
        assert hw.compute_capability == ""

    def test_to_dict_has_platform_value(self):
        hw = self._make()
        d = hw.to_dict()
        assert d["platform"] == "cpu"

    def test_to_dict_all_keys(self):
        hw = self._make()
        d = hw.to_dict()
        for key in ["platform", "device_name", "device_id", "total_memory_gb",
                    "compute_capability", "driver_version", "architecture"]:
            assert key in d

    def test_to_dict_custom_values(self):
        from ollama_arena.telemetry.base import HardwarePlatform
        hw = self._make(
            platform=HardwarePlatform.NVIDIA,
            device_name="RTX 4090",
            total_memory_gb=24.0,
        )
        d = hw.to_dict()
        assert d["platform"] == "nvidia"
        assert d["device_name"] == "RTX 4090"
        assert d["total_memory_gb"] == 24.0


# ──────────────────────────────────────────────────────────────────────────────
# TelemetryRecord
# ──────────────────────────────────────────────────────────────────────────────

class TestTelemetryRecord:
    def _make(self, **kw):
        from ollama_arena.telemetry.base import TelemetryRecord
        defaults = dict(timestamp=1000.0, model="llama3:8b", backend="ollama")
        defaults.update(kw)
        return TelemetryRecord(**defaults)

    def test_basic_creation(self):
        r = self._make()
        assert r.model == "llama3:8b"
        assert r.backend == "ollama"

    def test_default_zeros(self):
        r = self._make()
        assert r.tokens_in == 0
        assert r.tokens_out == 0
        assert r.latency_s == 0.0
        assert r.tps == 0.0
        assert r.power_w == 0.0
        assert r.energy_j == 0.0

    def test_to_dict_has_all_keys(self):
        r = self._make()
        d = r.to_dict()
        for key in ["timestamp", "model", "backend", "tokens_in", "tokens_out",
                    "latency_s", "tps", "power_w", "energy_j", "tokens_per_watt",
                    "memory_used_gb", "category", "quantization"]:
            assert key in d

    def test_to_dict_values(self):
        r = self._make(model="phi3:3b", tps=42.0, tokens_out=100)
        d = r.to_dict()
        assert d["model"] == "phi3:3b"
        assert d["tps"] == 42.0
        assert d["tokens_out"] == 100

    def test_default_empty_hardware_info(self):
        r = self._make()
        assert r.hardware_info == {}

    def test_custom_hardware_info(self):
        r = self._make(hardware_info={"gpu": "RTX4090"})
        assert r.hardware_info["gpu"] == "RTX4090"


# ──────────────────────────────────────────────────────────────────────────────
# HardwareDetector — detect() runs without crashing
# ──────────────────────────────────────────────────────────────────────────────

class TestHardwareDetector:
    def test_detect_platform_returns_valid(self):
        from ollama_arena.telemetry.base import HardwareDetector, HardwarePlatform
        platform = HardwareDetector.detect_platform()
        assert isinstance(platform, HardwarePlatform)

    def test_detect_platform_is_known(self):
        from ollama_arena.telemetry.base import HardwareDetector, HardwarePlatform
        platform = HardwareDetector.detect_platform()
        assert platform in list(HardwarePlatform)

    def test_has_nvidia_returns_bool(self):
        from ollama_arena.telemetry.base import HardwareDetector
        result = HardwareDetector._has_nvidia()
        assert isinstance(result, bool)
