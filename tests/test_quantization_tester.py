"""Tests for QuantizationTester — pure paths and mock subprocess calls."""
from __future__ import annotations

import unittest.mock as mock

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# QuantizationTester — init and pure methods
# ──────────────────────────────────────────────────────────────────────────────

class TestQuantizationTesterInit:
    def _make(self):
        from ollama_arena.telemetry.quantization import QuantizationTester
        return QuantizationTester()

    def test_init_does_not_crash(self):
        t = self._make()
        assert t is not None

    def test_results_initially_empty(self):
        t = self._make()
        assert t.results == []

    def test_hardware_detected(self):
        from ollama_arena.telemetry.base import HardwareInfo
        t = self._make()
        assert isinstance(t.hardware, HardwareInfo)

    def test_backend_url_default(self):
        t = self._make()
        assert "localhost" in t.backend_url or "11434" in t.backend_url

    def test_custom_backend_url(self):
        from ollama_arena.telemetry.quantization import QuantizationTester
        t = QuantizationTester(backend_url="http://remote:11434")
        assert t.backend_url == "http://remote:11434"


class TestQuantizationTesterPureMethods:
    def _make(self):
        from ollama_arena.telemetry.quantization import QuantizationTester
        return QuantizationTester()

    def test_extract_param_count_7b(self):
        t = self._make()
        assert t._extract_param_count("llama2-7B") == 7_000_000_000

    def test_extract_param_count_13b(self):
        t = self._make()
        assert t._extract_param_count("llama2-13b") == 13_000_000_000

    def test_extract_param_count_70b(self):
        t = self._make()
        assert t._extract_param_count("llama2-70B") == 70_000_000_000

    def test_extract_param_count_unknown_defaults(self):
        t = self._make()
        result = t._extract_param_count("unknown-model")
        assert result == 7_000_000_000

    def test_estimate_vram_q4_km(self):
        from ollama_arena.telemetry.quantization import QuantizationFormat
        t = self._make()
        vram = t._estimate_vram_usage("llama2-7B", QuantizationFormat.Q4_K_M)
        assert isinstance(vram, float)
        assert vram > 0

    def test_estimate_vram_fp16_larger_than_q4(self):
        from ollama_arena.telemetry.quantization import QuantizationFormat
        t = self._make()
        vram_q4 = t._estimate_vram_usage("llama2-7B", QuantizationFormat.Q4_K_M)
        vram_fp16 = t._estimate_vram_usage("llama2-7B", QuantizationFormat.FP16)
        assert vram_fp16 > vram_q4

    def test_get_model_size_fallback(self):
        from ollama_arena.telemetry.quantization import QuantizationFormat
        t = self._make()
        # When ollama subprocess fails, fallback estimate is used
        with mock.patch("subprocess.run", side_effect=FileNotFoundError("ollama not found")):
            size = t.get_model_size("llama2", QuantizationFormat.Q4_K_M)
        assert isinstance(size, float)
        assert size > 0

    def test_get_model_size_q4_km_estimate(self):
        from ollama_arena.telemetry.quantization import QuantizationFormat
        t = self._make()
        with mock.patch("subprocess.run", side_effect=Exception("fail")):
            size = t.get_model_size("llama2", QuantizationFormat.Q4_K_M)
        assert size == pytest.approx(4.0)

    def test_get_model_size_fp16_estimate(self):
        from ollama_arena.telemetry.quantization import QuantizationFormat
        t = self._make()
        with mock.patch("subprocess.run", side_effect=Exception("fail")):
            size = t.get_model_size("llama2", QuantizationFormat.FP16)
        assert size == pytest.approx(14.0)

    def test_get_model_size_unknown_format_default(self):
        from ollama_arena.telemetry.quantization import QuantizationFormat
        t = self._make()
        with mock.patch("subprocess.run", side_effect=Exception("fail")):
            size = t.get_model_size("llama2", QuantizationFormat.IQ4_NL)
        assert isinstance(size, float)


class TestQuantizationTesterListFormats:
    def _make(self):
        from ollama_arena.telemetry.quantization import QuantizationTester
        return QuantizationTester()

    def test_list_formats_ollama_not_found_returns_fallback(self):
        from ollama_arena.telemetry.quantization import QuantizationFormat
        t = self._make()
        with mock.patch("subprocess.run", side_effect=FileNotFoundError):
            formats = t.list_available_formats("llama2")
        assert QuantizationFormat.Q4_K_M in formats
        assert QuantizationFormat.Q8_0 in formats

    def test_list_formats_subprocess_error_returns_fallback(self):
        from ollama_arena.telemetry.quantization import QuantizationFormat
        t = self._make()
        with mock.patch("subprocess.run", side_effect=Exception("timeout")):
            formats = t.list_available_formats("llama2")
        assert len(formats) >= 3

    def test_list_formats_no_duplicates(self):
        t = self._make()
        with mock.patch("subprocess.run", side_effect=Exception("fail")):
            formats = t.list_available_formats("llama2")
        assert len(formats) == len(set(formats))


class TestQuantizationTesterDownload:
    def _make(self):
        from ollama_arena.telemetry.quantization import QuantizationTester
        return QuantizationTester()

    def test_download_returns_false_when_ollama_fails(self):
        from ollama_arena.telemetry.quantization import QuantizationFormat
        t = self._make()
        mock_result = mock.MagicMock()
        mock_result.returncode = 1
        with mock.patch("subprocess.run", return_value=mock_result):
            result = t.download_model("llama2", QuantizationFormat.Q4_K_M)
        assert result is False

    def test_download_returns_true_when_ollama_succeeds(self):
        from ollama_arena.telemetry.quantization import QuantizationFormat
        t = self._make()
        mock_result = mock.MagicMock()
        mock_result.returncode = 0
        with mock.patch("subprocess.run", return_value=mock_result):
            result = t.download_model("llama2", QuantizationFormat.Q4_K_M)
        assert result is True

    def test_download_exception_returns_false(self):
        from ollama_arena.telemetry.quantization import QuantizationFormat
        t = self._make()
        with mock.patch("subprocess.run", side_effect=Exception("fail")):
            result = t.download_model("llama2", QuantizationFormat.Q4_K_M)
        assert result is False


class TestQuantizationTesterRunInference:
    def _make(self):
        from ollama_arena.telemetry.quantization import QuantizationTester
        return QuantizationTester()

    def test_run_inference_failure_returns_none(self):
        t = self._make()
        with mock.patch("subprocess.run", side_effect=Exception("fail")):
            result = t._run_inference("llama2:q4_k_m", "Hello")
        assert result is None

    def test_run_inference_nonzero_returncode_returns_none(self):
        t = self._make()
        mock_result = mock.MagicMock()
        mock_result.returncode = 1
        with mock.patch("subprocess.run", return_value=mock_result):
            result = t._run_inference("llama2:q4_k_m", "Hello")
        assert result is None

    def test_run_inference_success_returns_dict(self):
        t = self._make()
        mock_result = mock.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Hello world this is a response with many tokens"
        with mock.patch("subprocess.run", return_value=mock_result):
            result = t._run_inference("llama2:q4_k_m", "Hello")
        assert result is not None
        assert "latency_s" in result
        assert "tps" in result
