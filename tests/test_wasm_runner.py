"""Tests for sandboxes/wasm_runner.py."""
from __future__ import annotations
import sys
import unittest.mock as mock
import pytest


class TestWasmAvailable:
    def test_false_when_no_wasmtime(self):
        from ollama_arena.sandboxes.wasm_runner import wasm_available
        with mock.patch.dict(sys.modules, {"wasmtime": None}):
            result = wasm_available()
        assert result is False

    def test_true_when_wasmtime_present(self):
        from ollama_arena.sandboxes.wasm_runner import wasm_available
        mock_wasmtime = mock.MagicMock()
        with mock.patch.dict(sys.modules, {"wasmtime": mock_wasmtime}):
            result = wasm_available()
        assert result is True

    def test_alias(self):
        from ollama_arena.sandboxes.wasm_runner import _wasmtime_available, wasm_available
        assert _wasmtime_available is wasm_available


class TestRunPythonWasm:
    def test_no_wasmtime_returns_error(self):
        from ollama_arena.sandboxes.wasm_runner import _run_python_wasm
        with mock.patch.dict(sys.modules, {"wasmtime": None}):
            result = _run_python_wasm("print(1)", 5)
        assert result.accepted is False
        assert "not installed" in result.error

    def test_simple_print_int(self):
        from ollama_arena.sandboxes.wasm_runner import _run_python_wasm
        mock_wasmtime = mock.MagicMock()
        with mock.patch.dict(sys.modules, {"wasmtime": mock_wasmtime}):
            result = _run_python_wasm("print(1 + 2)", 5)
        assert result.accepted is True
        assert "3" in result.output
        assert result.language == "python"

    def test_simple_print_string(self):
        from ollama_arena.sandboxes.wasm_runner import _run_python_wasm
        mock_wasmtime = mock.MagicMock()
        with mock.patch.dict(sys.modules, {"wasmtime": mock_wasmtime}):
            result = _run_python_wasm('print("hello")', 5)
        assert result.accepted is True
        assert "hello" in result.output

    def test_print_eval_error(self):
        from ollama_arena.sandboxes.wasm_runner import _run_python_wasm
        mock_wasmtime = mock.MagicMock()
        with mock.patch.dict(sys.modules, {"wasmtime": mock_wasmtime}):
            # Division by zero inside print()
            result = _run_python_wasm("print(1/0)", 5)
        assert result.accepted is False
        assert result.error  # should have error message

    def test_non_print_code_returns_unsupported(self):
        from ollama_arena.sandboxes.wasm_runner import _run_python_wasm
        mock_wasmtime = mock.MagicMock()
        # wasmtime Module/Engine/Store mock
        mock_engine = mock.MagicMock()
        mock_module = mock.MagicMock()
        mock_store = mock.MagicMock()
        mock_instance = mock.MagicMock()
        mock_exports = mock.MagicMock()
        mock_exports.__getitem__ = mock.MagicMock(return_value=mock.MagicMock())
        mock_instance.exports.return_value = mock_exports
        mock_wasmtime.Engine.return_value = mock_engine
        mock_wasmtime.Module.return_value = mock_module
        mock_wasmtime.Store.return_value = mock_store
        mock_wasmtime.Instance.return_value = mock_instance
        with mock.patch.dict(sys.modules, {"wasmtime": mock_wasmtime}):
            result = _run_python_wasm("x = 1\ny = 2\nprint(x + y)", 5)
        assert result.accepted is False
        assert "WASM sandbox" in result.error or result.error

    def test_wasm_probe_exception_continues(self):
        from ollama_arena.sandboxes.wasm_runner import _run_python_wasm
        mock_wasmtime = mock.MagicMock()
        mock_wasmtime.Engine.side_effect = Exception("engine failed")
        with mock.patch.dict(sys.modules, {"wasmtime": mock_wasmtime}):
            result = _run_python_wasm("for i in range(10): pass", 5)
        # Engine failed but we still get a result
        assert result.error is not None
        assert result.language == "python"

    def test_duration_set(self):
        from ollama_arena.sandboxes.wasm_runner import _run_python_wasm
        mock_wasmtime = mock.MagicMock()
        with mock.patch.dict(sys.modules, {"wasmtime": mock_wasmtime}):
            result = _run_python_wasm("print(42)", 5)
        assert result.duration_s >= 0.0


class TestRunJavascriptWasm:
    def test_no_wasmtime_returns_error(self):
        from ollama_arena.sandboxes.wasm_runner import _run_javascript_wasm
        with mock.patch("ollama_arena.sandboxes.wasm_runner.wasm_available", return_value=False):
            result = _run_javascript_wasm("console.log(1)", 5)
        assert result.accepted is False
        assert "not installed" in result.error
        assert result.language == "javascript"

    def test_wasmtime_present_returns_unsupported_msg(self):
        from ollama_arena.sandboxes.wasm_runner import _run_javascript_wasm
        with mock.patch("ollama_arena.sandboxes.wasm_runner.wasm_available", return_value=True):
            result = _run_javascript_wasm("console.log(1)", 5)
        assert result.accepted is False
        assert "JS" in result.error or "Docker" in result.error
        assert result.language == "javascript"

    def test_duration_set(self):
        from ollama_arena.sandboxes.wasm_runner import _run_javascript_wasm
        with mock.patch("ollama_arena.sandboxes.wasm_runner.wasm_available", return_value=True):
            result = _run_javascript_wasm("x=1", 5)
        assert result.duration_s >= 0.0


class TestRunInWasm:
    def test_python(self):
        from ollama_arena.sandboxes.wasm_runner import run_in_wasm
        mock_wasmtime = mock.MagicMock()
        with mock.patch.dict(sys.modules, {"wasmtime": mock_wasmtime}):
            result = run_in_wasm("print(5)", "python", timeout=5)
        assert result.language == "python"

    def test_javascript(self):
        from ollama_arena.sandboxes.wasm_runner import run_in_wasm
        with mock.patch("ollama_arena.sandboxes.wasm_runner.wasm_available", return_value=True):
            result = run_in_wasm("console.log(1)", "javascript", timeout=5)
        assert result.language == "javascript"

    def test_unsupported_language(self):
        from ollama_arena.sandboxes.wasm_runner import run_in_wasm
        result = run_in_wasm("code", "rust", timeout=5)
        assert result.accepted is False
        assert "not supported" in result.error.lower() or "rust" in result.error.lower()

    def test_language_enum_python(self):
        from ollama_arena.sandboxes.wasm_runner import run_in_wasm
        from ollama_arena.sandboxes.base import Language
        mock_wasmtime = mock.MagicMock()
        with mock.patch.dict(sys.modules, {"wasmtime": mock_wasmtime}):
            result = run_in_wasm("print(1)", Language.PYTHON, timeout=5)
        assert result.language == "python"

    def test_language_enum_javascript(self):
        from ollama_arena.sandboxes.wasm_runner import run_in_wasm
        from ollama_arena.sandboxes.base import Language
        with mock.patch("ollama_arena.sandboxes.wasm_runner.wasm_available", return_value=False):
            result = run_in_wasm("x=1", Language.JAVASCRIPT, timeout=5)
        assert result.language == "javascript"
