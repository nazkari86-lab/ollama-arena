"""Tests for backends/transformers_backend.py."""
from __future__ import annotations
import sys
import time
import unittest.mock as mock
import pytest


def _make_backend(**kwargs):
    from ollama_arena.backends.transformers_backend import TransformersBackend
    return TransformersBackend(**kwargs)


class TestTransformersBackendInit:
    def test_defaults(self):
        b = _make_backend()
        assert b.name == "transformers"
        assert b.default_model is None
        assert b.device == "auto"
        assert b.torch_dtype == "auto"
        assert b.cache_dir is None
        assert b._cache == {}

    def test_custom_args(self):
        b = _make_backend(
            default_model="phi3:mini",
            device="cpu",
            torch_dtype="float32",
            cache_dir="/tmp/cache",
        )
        assert b.default_model == "phi3:mini"
        assert b.device == "cpu"
        assert b.torch_dtype == "float32"
        assert b.cache_dir == "/tmp/cache"


class TestTransformersBackendIsAlive:
    def test_alive_when_torch_present(self):
        b = _make_backend()
        mock_torch = mock.MagicMock()
        mock_transformers = mock.MagicMock()
        with mock.patch.dict(sys.modules, {
            "torch": mock_torch,
            "transformers": mock_transformers,
        }):
            assert b.is_alive() is True

    def test_not_alive_when_torch_missing(self):
        b = _make_backend()
        with mock.patch.dict(sys.modules, {"torch": None, "transformers": None}):
            assert b.is_alive() is False


class TestTransformersBackendListModels:
    def test_empty_cache_no_default(self):
        b = _make_backend()
        assert b.list_models() == []

    def test_empty_cache_with_default(self):
        b = _make_backend(default_model="llama3:8b")
        assert b.list_models() == ["llama3:8b"]

    def test_with_cache(self):
        b = _make_backend()
        b._cache["model1"] = (mock.MagicMock(), mock.MagicMock())
        assert "model1" in b.list_models()

    def test_cache_and_default(self):
        b = _make_backend(default_model="default_model")
        b._cache["cached_model"] = (mock.MagicMock(), mock.MagicMock())
        models = b.list_models()
        assert "cached_model" in models
        assert "default_model" in models


class TestTransformersBackendLoad:
    def test_load_raises_when_torch_missing(self):
        b = _make_backend()
        with mock.patch.dict(sys.modules, {"torch": None, "transformers": None}):
            with pytest.raises(RuntimeError, match="pip install"):
                b._load("any_model")

    def test_load_returns_cached(self):
        b = _make_backend()
        fake_model = mock.MagicMock()
        fake_tok = mock.MagicMock()
        b._cache["cached_model"] = (fake_model, fake_tok)
        result = b._load("cached_model")
        assert result == (fake_model, fake_tok)

    def test_load_success_with_mocked_deps(self):
        b = _make_backend(device="cpu", torch_dtype="auto")
        mock_torch = mock.MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.float32 = "float32"
        mock_torch.bfloat16 = "bfloat16"

        mock_transformers = mock.MagicMock()
        mock_tok = mock.MagicMock()
        mock_tok.pad_token = None
        mock_tok.eos_token = "<eos>"
        mock_transformers.AutoTokenizer.from_pretrained.return_value = mock_tok

        mock_model = mock.MagicMock()
        mock_transformers.AutoModelForCausalLM.from_pretrained.return_value = mock_model

        with mock.patch.dict(sys.modules, {
            "torch": mock_torch,
            "transformers": mock_transformers,
        }):
            model, tok = b._load("test_model")

        assert model is mock_model
        assert tok is mock_tok
        mock_model.eval.assert_called_once()
        assert "test_model" in b._cache

    def test_load_explicit_dtype(self):
        b = _make_backend(torch_dtype="float16")
        mock_torch = mock.MagicMock()
        mock_transformers = mock.MagicMock()
        mock_tok = mock.MagicMock()
        mock_tok.pad_token = "pad"
        mock_transformers.AutoTokenizer.from_pretrained.return_value = mock_tok
        mock_model = mock.MagicMock()
        mock_transformers.AutoModelForCausalLM.from_pretrained.return_value = mock_model

        with mock.patch.dict(sys.modules, {
            "torch": mock_torch,
            "transformers": mock_transformers,
        }):
            b._load("my_model")

        # torch_dtype="float16" skips the auto-detect branch
        mock_torch.cuda.is_available.assert_not_called()


class TestTransformersBackendChatTurn:
    def _make_mocks(self, output_text="hello", tokens_in=10, tokens_out=5):
        mock_torch = mock.MagicMock()
        mock_torch.inference_mode.return_value.__enter__ = mock.MagicMock(return_value=None)
        mock_torch.inference_mode.return_value.__exit__ = mock.MagicMock(return_value=False)
        mock_transformers = mock.MagicMock()
        mock_tok = mock.MagicMock()
        mock_tok.pad_token = "pad"
        mock_tok.pad_token_id = 0
        mock_tok.apply_chat_template.return_value = "formatted prompt"
        mock_tok.decode.return_value = output_text

        fake_inputs = mock.MagicMock()
        fake_input_ids = mock.MagicMock()
        fake_input_ids.shape = [1, tokens_in]
        fake_inputs.__getitem__ = lambda self, key: fake_input_ids if key == "input_ids" else mock.MagicMock()
        fake_inputs.to.return_value = fake_inputs
        mock_tok.return_value = fake_inputs

        fake_out = mock.MagicMock()
        fake_out.shape = [1, tokens_in + tokens_out]
        mock_model = mock.MagicMock()
        mock_model.device = "cpu"
        mock_model.generate.return_value = fake_out

        mock_transformers.AutoTokenizer.from_pretrained.return_value = mock_tok
        mock_transformers.AutoModelForCausalLM.from_pretrained.return_value = mock_model
        return mock_torch, mock_transformers, mock_model, mock_tok

    def test_chat_turn_success(self):
        b = _make_backend(device="cpu")
        mock_torch, mock_transformers, mock_model, mock_tok = self._make_mocks("Answer")

        with mock.patch.dict(sys.modules, {
            "torch": mock_torch,
            "transformers": mock_transformers,
        }):
            result = b.chat_turn("test_model", [{"role": "user", "content": "Hi"}], tools=[])

        assert result.error is None or result.error == ""
        assert result.text == "Answer"
        assert result.tokens_in == 10
        assert result.tokens_out == 5

    def test_chat_turn_load_error(self):
        b = _make_backend()
        with mock.patch.dict(sys.modules, {"torch": None, "transformers": None}):
            result = b.chat_turn("bad_model", [{"role": "user", "content": "X"}], tools=[])
        assert result.error

    def test_chat_turn_fallback_template(self):
        """When apply_chat_template raises, falls back to manual format."""
        b = _make_backend(device="cpu")
        mock_torch, mock_transformers, mock_model, mock_tok = self._make_mocks("Out")
        mock_tok.apply_chat_template.side_effect = Exception("no template")

        with mock.patch.dict(sys.modules, {
            "torch": mock_torch,
            "transformers": mock_transformers,
        }):
            result = b.chat_turn("test_model", [{"role": "user", "content": "Hi"}], tools=[])

        # Should still produce output, not crash
        assert result.text == "Out"

    def test_chat_turn_with_temperature(self):
        b = _make_backend(device="cpu")
        mock_torch, mock_transformers, mock_model, mock_tok = self._make_mocks("With temp")

        with mock.patch.dict(sys.modules, {
            "torch": mock_torch,
            "transformers": mock_transformers,
        }):
            result = b.chat_turn("test_model", [{"role": "user", "content": "Hi"}], tools=[], temperature=0.7)

        assert result.text == "With temp"

    def test_chat_turn_generate_failure_returns_error_not_raise(self):
        """model.generate() can raise for real reasons (CUDA OOM, shape
        mismatch, etc.) — chat_turn must report this as ChatTurnResult.error
        like every other backend, not let the exception propagate and crash
        the caller (e.g. an agent loop mid-run)."""
        b = _make_backend(device="cpu")
        mock_torch, mock_transformers, mock_model, mock_tok = self._make_mocks("unused")
        mock_model.generate.side_effect = RuntimeError("CUDA out of memory")

        with mock.patch.dict(sys.modules, {
            "torch": mock_torch,
            "transformers": mock_transformers,
        }):
            result = b.chat_turn("test_model", [{"role": "user", "content": "Hi"}], tools=[])

        assert result.error
        assert "CUDA out of memory" in result.error


class TestTransformersBackendGenerate:
    def test_generate_delegates_to_generate_with_tools(self):
        b = _make_backend()
        fake_result = mock.MagicMock()
        with mock.patch.object(b, "generate_with_tools", return_value=fake_result) as mock_gwt:
            result = b.generate("my_model", "prompt text")
        mock_gwt.assert_called_once()
        assert result is fake_result

    def test_generate_with_images(self):
        b = _make_backend()
        fake_result = mock.MagicMock()
        with mock.patch.object(b, "generate_with_tools", return_value=fake_result) as mock_gwt:
            b.generate("my_model", "describe this", images=["img_data"])
        # images should be stripped from opts and added to message
        call_args = mock_gwt.call_args
        messages = call_args[0][1]
        assert messages[0]["images"] == ["img_data"]


class TestTransformersBackendGenerateWithTools:
    def test_success(self):
        b = _make_backend()
        from ollama_arena.backends.base import ChatTurnResult
        fake_turn = ChatTurnResult(
            text="response",
            tool_calls=[],
            tokens_in=10,
            tokens_out=20,
            latency_s=0.5,
            time_to_first=0.5,
            finish_reason="stop",
        )
        with mock.patch.object(b, "chat_turn", return_value=fake_turn):
            result = b.generate_with_tools("m", [{"role": "user", "content": "x"}], tools=[])

        assert result.text == "response"
        assert result.tps == pytest.approx(40.0)
        assert result.backend_type == "transformers"

    def test_error_propagates(self):
        b = _make_backend()
        from ollama_arena.backends.base import ChatTurnResult
        fake_turn = ChatTurnResult(error="load failed", latency_s=0.0)
        with mock.patch.object(b, "chat_turn", return_value=fake_turn):
            result = b.generate_with_tools("m", [], tools=[])

        assert result.error == "load failed"
        assert result.text == ""

    def test_zero_latency_no_div_by_zero(self):
        b = _make_backend()
        from ollama_arena.backends.base import ChatTurnResult
        fake_turn = ChatTurnResult(
            text="hi",
            tool_calls=[],
            tokens_in=5,
            tokens_out=5,
            latency_s=0.0,
            time_to_first=0.0,
            finish_reason="stop",
        )
        with mock.patch.object(b, "chat_turn", return_value=fake_turn):
            result = b.generate_with_tools("m", [], tools=[])
        assert result.tps == 0.0
