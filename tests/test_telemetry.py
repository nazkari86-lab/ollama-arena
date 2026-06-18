"""Tests for the telemetry module dataclasses and enums."""
import time

import pytest


class TestHardwarePlatform:
    def test_all_platforms(self):
        from ollama_arena.telemetry.base import HardwarePlatform
        assert HardwarePlatform.NVIDIA  == HardwarePlatform("nvidia")
        assert HardwarePlatform.AMD     == HardwarePlatform("amd")
        assert HardwarePlatform.APPLE   == HardwarePlatform("apple")
        assert HardwarePlatform.CPU     == HardwarePlatform("cpu")
        assert HardwarePlatform.UNKNOWN == HardwarePlatform("unknown")
        assert len(HardwarePlatform) == 5

    def test_platform_value(self):
        from ollama_arena.telemetry.base import HardwarePlatform
        assert HardwarePlatform.NVIDIA.value == "nvidia"


class TestHardwareInfo:
    def test_defaults(self):
        from ollama_arena.telemetry.base import HardwareInfo, HardwarePlatform
        info = HardwareInfo(platform=HardwarePlatform.CPU)
        assert info.platform == HardwarePlatform.CPU
        assert info.device_name == ""
        assert info.total_memory_gb == 0.0

    def test_custom(self):
        from ollama_arena.telemetry.base import HardwareInfo, HardwarePlatform
        info = HardwareInfo(
            platform=HardwarePlatform.APPLE,
            device_name="M3 Pro",
            total_memory_gb=36.0,
            architecture="arm64",
        )
        assert info.total_memory_gb == 36.0
        assert info.architecture == "arm64"

    def test_to_dict(self):
        from ollama_arena.telemetry.base import HardwareInfo, HardwarePlatform
        info = HardwareInfo(
            platform=HardwarePlatform.NVIDIA,
            device_name="RTX 4090",
            total_memory_gb=24.0,
        )
        d = info.to_dict()
        assert d["platform"] == "nvidia"
        assert d["device_name"] == "RTX 4090"
        assert d["total_memory_gb"] == 24.0


class TestTelemetryRecord:
    def test_defaults(self):
        from ollama_arena.telemetry.base import TelemetryRecord
        rec = TelemetryRecord(timestamp=time.time(), model="llama3", backend="ollama")
        assert rec.tokens_in == 0
        assert rec.power_w == 0.0
        assert rec.category == ""
        assert isinstance(rec.hardware_info, dict)

    def test_to_dict(self):
        from ollama_arena.telemetry.base import TelemetryRecord
        rec = TelemetryRecord(
            timestamp=1700000000.0, model="phi3", backend="ollama",
            tokens_out=128, latency_s=2.5, tps=51.2, category="code",
        )
        d = rec.to_dict()
        assert d["model"] == "phi3"
        assert d["tokens_out"] == 128
        assert d["tps"] == 51.2
        assert d["category"] == "code"

    def test_energy_fields(self):
        from ollama_arena.telemetry.base import TelemetryRecord
        rec = TelemetryRecord(
            timestamp=0.0, model="x", backend="y",
            power_w=150.0, energy_j=375.0, tokens_per_watt=2.5,
        )
        assert rec.power_w == 150.0
        assert rec.tokens_per_watt == 2.5


class TestTelemetryModuleImports:
    def test_bandwidth_module(self):
        from ollama_arena.telemetry import bandwidth  # noqa: F401
        assert hasattr(bandwidth, "__file__")

    def test_energy_module(self):
        from ollama_arena.telemetry import energy  # noqa: F401
        assert hasattr(energy, "__file__")

    def test_quantization_module(self):
        from ollama_arena.telemetry import quantization  # noqa: F401
        assert hasattr(quantization, "__file__")

    def test_base_module_classes(self):
        from ollama_arena.telemetry.base import (
            HardwarePlatform, HardwareInfo, TelemetryRecord,
        )
        assert HardwarePlatform
        assert HardwareInfo
        assert TelemetryRecord
