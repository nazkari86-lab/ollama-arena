"""Tests for model_caps auto-detection module."""
from __future__ import annotations

import threading
import time
import unittest.mock as mock

import pytest


def _make_show_response(
    families: list[str] | None = None,
    modelfile: str = "",
    context_length: int = 4096,
    status: int = 200,
):
    """Build a mock response matching Ollama /api/show output."""
    r = mock.MagicMock()
    r.status_code = status
    r.json = mock.MagicMock(return_value={
        "details": {
            "families": families or [],
            "context_length": context_length,
        },
        "modelfile": modelfile,
        "model_info": {},
    })
    return r


# ──────────────────────────────────────────────────────────────────────────────
# _param_size
# ──────────────────────────────────────────────────────────────────────────────

class TestParamSize:
    def test_7b_detected(self):
        from ollama_arena.model_caps import _param_size
        assert _param_size("llama3:7b") == "7B"

    def test_70b_detected(self):
        from ollama_arena.model_caps import _param_size
        assert _param_size("llama3:70b-instruct") == "70B"

    def test_float_param(self):
        from ollama_arena.model_caps import _param_size
        assert _param_size("phi-3.5B") == "3.5B"

    def test_unknown_returns_question_mark(self):
        from ollama_arena.model_caps import _param_size
        assert _param_size("unknown-model") == "?"

    def test_case_insensitive_b(self):
        from ollama_arena.model_caps import _param_size
        assert _param_size("model-13B") == "13B"


# ──────────────────────────────────────────────────────────────────────────────
# _detect_one — vision / tools / ctx detection
# ──────────────────────────────────────────────────────────────────────────────

class TestDetectOne:
    def test_vision_detected_via_clip_family(self):
        from ollama_arena.model_caps import _detect_one
        resp = _make_show_response(families=["llama", "clip"])
        with mock.patch("requests.post", return_value=resp):
            caps = _detect_one("llava:7b", "http://localhost:11434")
        assert caps["vision"] is True

    def test_vision_false_for_plain_model(self):
        from ollama_arena.model_caps import _detect_one
        resp = _make_show_response(families=["llama"])
        with mock.patch("requests.post", return_value=resp):
            caps = _detect_one("llama3:7b", "http://localhost:11434")
        assert caps["vision"] is False

    def test_tools_detected_via_template_marker(self):
        from ollama_arena.model_caps import _detect_one
        resp = _make_show_response(
            families=["llama"],
            modelfile='TEMPLATE """{{ .ToolCalls }}"""',
        )
        with mock.patch("requests.post", return_value=resp):
            caps = _detect_one("llama3.1:8b", "http://localhost:11434")
        assert caps["tools"] is True

    def test_tools_false_when_no_markers(self):
        from ollama_arena.model_caps import _detect_one
        resp = _make_show_response(families=["llama"], modelfile="plain template")
        with mock.patch("requests.post", return_value=resp):
            caps = _detect_one("llama3:7b", "http://localhost:11434")
        assert caps["tools"] is False

    def test_tool_call_marker_detected(self):
        from ollama_arena.model_caps import _detect_one
        resp = _make_show_response(
            families=["qwen"],
            modelfile="<tool_call>some marker</tool_call>",
        )
        with mock.patch("requests.post", return_value=resp):
            caps = _detect_one("qwen2.5:7b", "http://localhost:11434")
        assert caps["tools"] is True

    def test_ctx_length_extracted(self):
        from ollama_arena.model_caps import _detect_one
        resp = _make_show_response(families=["llama"], context_length=32768)
        with mock.patch("requests.post", return_value=resp):
            caps = _detect_one("llama3:7b", "http://localhost:11434")
        assert caps["ctx_length"] == 32768

    def test_families_normalized_lowercase(self):
        from ollama_arena.model_caps import _detect_one
        resp = _make_show_response(families=["Llama", "CLIP"])
        with mock.patch("requests.post", return_value=resp):
            caps = _detect_one("llava:7b", "http://localhost:11434")
        assert "llama" in caps["families"]
        assert "clip" in caps["families"]

    def test_http_error_returns_empty(self):
        from ollama_arena.model_caps import _detect_one
        resp = _make_show_response(status=404)
        with mock.patch("requests.post", return_value=resp):
            caps = _detect_one("nonexistent:7b", "http://localhost:11434")
        assert caps == {}

    def test_connection_error_returns_empty(self):
        from ollama_arena.model_caps import _detect_one
        with mock.patch("requests.post", side_effect=ConnectionError("refused")):
            caps = _detect_one("llama3:7b", "http://localhost:11434")
        assert caps == {}

    def test_param_size_in_result(self):
        from ollama_arena.model_caps import _detect_one
        resp = _make_show_response(families=["llama"])
        with mock.patch("requests.post", return_value=resp):
            caps = _detect_one("llama3:7b", "http://localhost:11434")
        assert caps["param_size"] == "7B"


# ──────────────────────────────────────────────────────────────────────────────
# get() — caching and TTL
# ──────────────────────────────────────────────────────────────────────────────

class TestGetCaching:
    def setup_method(self):
        """Clear cache before each test."""
        from ollama_arena import model_caps
        model_caps.invalidate()

    def _fake_resp(self, families=None, ctx=4096):
        return _make_show_response(families=families or ["llama"], context_length=ctx)

    def test_second_call_hits_cache(self):
        from ollama_arena.model_caps import get, invalidate
        invalidate()
        resp = self._fake_resp()
        with mock.patch("requests.post", return_value=resp) as m:
            get("llama3:7b", "http://localhost:11434")
            get("llama3:7b", "http://localhost:11434")
        # Only called once — second hit was cached
        assert m.call_count == 1

    def test_invalidate_single_model_forces_redetect(self):
        from ollama_arena.model_caps import get, invalidate
        invalidate()
        resp = self._fake_resp()
        with mock.patch("requests.post", return_value=resp) as m:
            get("llama3:7b", "http://localhost:11434")
            invalidate("llama3:7b")
            get("llama3:7b", "http://localhost:11434")
        assert m.call_count == 2

    def test_invalidate_all_clears_everything(self):
        from ollama_arena.model_caps import get, invalidate
        invalidate()
        resp = self._fake_resp()
        with mock.patch("requests.post", return_value=resp) as m:
            get("llama3:7b", "http://localhost:11434")
            get("phi3:3b", "http://localhost:11434")
            invalidate()
            get("llama3:7b", "http://localhost:11434")
        assert m.call_count == 3  # both cached, then one re-detected

    def test_ttl_expiry_forces_redetect(self):
        from ollama_arena import model_caps
        model_caps.invalidate()
        resp = self._fake_resp()
        # get() calls time.time() once per invocation → 2 calls total
        with mock.patch("requests.post", return_value=resp) as m:
            with mock.patch("ollama_arena.model_caps.time") as tm:
                tm.time.side_effect = [0.0, 9999.0]
                model_caps.get("llama3:7b", "http://localhost:11434")
                model_caps.get("llama3:7b", "http://localhost:11434")
        assert m.call_count == 2

    def test_within_ttl_no_redetect(self):
        from ollama_arena import model_caps
        model_caps.invalidate()
        resp = self._fake_resp()
        with mock.patch("requests.post", return_value=resp) as m:
            with mock.patch("ollama_arena.model_caps.time") as tm:
                tm.time.side_effect = [0.0, 60.0]
                model_caps.get("llama3:7b", "http://localhost:11434")
                model_caps.get("llama3:7b", "http://localhost:11434")
        assert m.call_count == 1


# ──────────────────────────────────────────────────────────────────────────────
# detect_all() — parallel detection
# ──────────────────────────────────────────────────────────────────────────────

class TestDetectAll:
    def setup_method(self):
        from ollama_arena import model_caps
        model_caps.invalidate()

    def test_all_models_detected(self):
        from ollama_arena.model_caps import detect_all, invalidate
        invalidate()
        resp = _make_show_response(families=["llama"])
        with mock.patch("requests.post", return_value=resp):
            results = detect_all(["llama3:7b", "phi3:3b"], "http://localhost:11434")
        assert "llama3:7b" in results
        assert "phi3:3b" in results

    def test_empty_list_returns_empty(self):
        from ollama_arena.model_caps import detect_all
        results = detect_all([], "http://localhost:11434")
        assert results == {}

    def test_parallel_calls_all_complete(self):
        from ollama_arena.model_caps import detect_all, invalidate
        invalidate()
        models = [f"model{i}:7b" for i in range(5)]
        resp = _make_show_response(families=["llama"])
        with mock.patch("requests.post", return_value=resp):
            results = detect_all(models, "http://localhost:11434")
        assert len(results) == 5
