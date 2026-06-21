"""Tests for BaseTelemetryCollector and HardwareDetector."""
from __future__ import annotations

import time

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# HardwareDetector extended
# ──────────────────────────────────────────────────────────────────────────────

class TestHardwareDetectorExtended:
    def test_get_hardware_info_returns_hardware_info(self):
        from ollama_arena.telemetry.base import HardwareDetector, HardwareInfo
        hw = HardwareDetector.get_hardware_info()
        assert isinstance(hw, HardwareInfo)

    def test_get_hardware_info_platform_valid(self):
        from ollama_arena.telemetry.base import HardwareDetector, HardwarePlatform
        hw = HardwareDetector.get_hardware_info()
        assert hw.platform in list(HardwarePlatform)

    def test_has_amd_returns_bool(self):
        from ollama_arena.telemetry.base import HardwareDetector
        if hasattr(HardwareDetector, "_has_amd"):
            result = HardwareDetector._has_amd()
            assert isinstance(result, bool)

    def test_has_apple_gpu_returns_bool(self):
        from ollama_arena.telemetry.base import HardwareDetector
        if hasattr(HardwareDetector, "_has_apple_gpu"):
            result = HardwareDetector._has_apple_gpu()
            assert isinstance(result, bool)

    def test_detect_platform_no_nvidia_when_mocked(self):
        import unittest.mock as mock
        from ollama_arena.telemetry.base import HardwareDetector, HardwarePlatform
        with mock.patch.object(HardwareDetector, "_has_nvidia", return_value=False):
            with mock.patch.object(HardwareDetector, "_has_amd", return_value=False, create=True):
                platform = HardwareDetector.detect_platform()
                assert isinstance(platform, HardwarePlatform)


# ──────────────────────────────────────────────────────────────────────────────
# BaseTelemetryCollector
# ──────────────────────────────────────────────────────────────────────────────

class TestBaseTelemetryCollector:
    def _make(self, tmp_path=None):
        from unittest.mock import MagicMock
        from ollama_arena.telemetry.base import BaseTelemetryCollector
        storage = MagicMock()
        return BaseTelemetryCollector(storage=storage), storage

    def test_init_does_not_crash(self):
        collector, _ = self._make()
        assert collector is not None

    def test_recording_start_initially_none(self):
        collector, _ = self._make()
        assert collector._recording_start is None

    def test_start_recording_sets_model(self):
        collector, _ = self._make()
        collector.start_recording("llama3:8b", "ollama")
        assert collector._current_model == "llama3:8b"
        assert collector._current_backend == "ollama"

    def test_start_recording_sets_timestamp(self):
        collector, _ = self._make()
        before = time.time()
        collector.start_recording("llama3:8b", "ollama")
        after = time.time()
        assert before <= collector._recording_start <= after

    def test_stop_recording_returns_telemetry_record(self):
        from ollama_arena.telemetry.base import TelemetryRecord
        collector, _ = self._make()
        collector.start_recording("phi3:3b", "ollama")
        record = collector.stop_recording(tokens_out=100, tps=42.0)
        assert isinstance(record, TelemetryRecord)
        assert record.model == "phi3:3b"
        assert record.tps == 42.0
        assert record.tokens_out == 100

    def test_stop_recording_clears_state(self):
        collector, _ = self._make()
        collector.start_recording("llama3:8b", "ollama")
        collector.stop_recording()
        assert collector._recording_start is None
        assert collector._current_model is None
        assert collector._current_backend is None

    def test_stop_recording_without_start_raises(self):
        collector, _ = self._make()
        with pytest.raises(RuntimeError, match="Recording not started"):
            collector.stop_recording()

    def test_stop_recording_sets_category(self):
        collector, _ = self._make()
        collector.start_recording("llama3:8b", "ollama")
        record = collector.stop_recording(category="coding")
        assert record.category == "coding"

    def test_stop_recording_sets_quantization(self):
        collector, _ = self._make()
        collector.start_recording("llama3:8b", "ollama")
        record = collector.stop_recording(quantization="q4_k_m")
        assert record.quantization == "q4_k_m"

    def test_record_generation_calls_storage_store(self):
        from ollama_arena.telemetry.base import TelemetryRecord
        collector, storage = self._make()
        r = TelemetryRecord(timestamp=time.time(), model="m", backend="b")
        collector.record_generation(r)
        storage.store.assert_called_once_with(r)

    def test_get_current_hardware_returns_hardware_info(self):
        from ollama_arena.telemetry.base import HardwareInfo
        collector, _ = self._make()
        hw = collector.get_current_hardware()
        assert isinstance(hw, HardwareInfo)

    def test_hardware_info_has_platform(self):
        from ollama_arena.telemetry.base import HardwarePlatform
        collector, _ = self._make()
        hw = collector.get_current_hardware()
        assert isinstance(hw.platform, HardwarePlatform)


# ──────────────────────────────────────────────────────────────────────────────
# get_telemetry_collector factory
# ──────────────────────────────────────────────────────────────────────────────

class TestGetTelemetryCollector:
    def test_factory_returns_base_collector(self, tmp_path):
        from ollama_arena.telemetry.base import get_telemetry_collector, BaseTelemetryCollector
        collector = get_telemetry_collector(db_path=str(tmp_path / "t.db"))
        assert isinstance(collector, BaseTelemetryCollector)

    def test_factory_uses_custom_storage(self):
        from unittest.mock import MagicMock
        from ollama_arena.telemetry.base import get_telemetry_collector, BaseTelemetryCollector
        storage = MagicMock()
        collector = get_telemetry_collector(storage=storage)
        assert collector.storage is storage

    def test_factory_with_no_args_creates_sqlite_storage(self, tmp_path):
        from ollama_arena.telemetry.base import get_telemetry_collector, SQLiteTelemetryStorage
        collector = get_telemetry_collector(db_path=str(tmp_path / "t.db"))
        assert isinstance(collector.storage, SQLiteTelemetryStorage)
