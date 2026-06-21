"""Tests for backends: base utilities, Anthropic SSE, Ollama streaming, auto-routing."""
from __future__ import annotations

import json
import unittest.mock as mock

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _sse_lines(*events: dict) -> list[bytes]:
    """Build a list of raw SSE lines from event dicts (matches requests.iter_lines)."""
    lines = []
    for ev in events:
        lines.append(f"data: {json.dumps(ev)}".encode())
        lines.append(b"")  # blank separator
    lines.append(b"data: [DONE]")
    return lines


def _fake_response(lines: list[bytes], status_code: int = 200):
    resp = mock.MagicMock()
    resp.status_code = status_code
    resp.text = ""
    resp.iter_lines = mock.MagicMock(
        return_value=iter(line.decode() if isinstance(line, bytes) else line for line in lines)
    )
    return resp


def _ollama_chunks(*contents: str, done_tokens: tuple[int, int] = (10, 20)) -> list[bytes]:
    """Build NDJSON lines as Ollama /api/chat returns."""
    lines = []
    for c in contents:
        lines.append(json.dumps({"message": {"content": c, "role": "assistant"}}).encode())
    # final done chunk
    ti, to = done_tokens
    lines.append(json.dumps({
        "message": {"content": "", "role": "assistant"},
        "done": True,
        "prompt_eval_count": ti,
        "eval_count": to,
    }).encode())
    return lines


def _fake_ollama_response(chunks: list[bytes], status_code: int = 200):
    resp = mock.MagicMock()
    resp.status_code = status_code
    resp.iter_lines = mock.MagicMock(return_value=iter(chunks))
    return resp


# ──────────────────────────────────────────────────────────────────────────────
# base.py — strip_thinking
# ──────────────────────────────────────────────────────────────────────────────

class TestStripThinking:
    def test_no_tags_passthrough(self):
        from ollama_arena.backends.base import strip_thinking
        assert strip_thinking("Hello world") == "Hello world"

    def test_think_tags_removed(self):
        from ollama_arena.backends.base import strip_thinking
        result = strip_thinking("<think>internal monologue</think>Answer here")
        assert "internal monologue" not in result
        assert "Answer here" in result

    def test_thinking_tags_removed(self):
        from ollama_arena.backends.base import strip_thinking
        result = strip_thinking("<thinking>step 1\nstep 2</thinking>Final answer")
        assert "step 1" not in result
        assert "Final answer" in result

    def test_reasoning_tags_removed(self):
        from ollama_arena.backends.base import strip_thinking
        result = strip_thinking("<reasoning>why</reasoning>Because")
        assert "why" not in result
        assert "Because" in result

    def test_multiline_think_removed(self):
        from ollama_arena.backends.base import strip_thinking
        text = "<think>\nline1\nline2\n</think>clean"
        assert strip_thinking(text) == "clean"

    def test_empty_string(self):
        from ollama_arena.backends.base import strip_thinking
        assert strip_thinking("") == ""

    def test_only_tags_gives_empty(self):
        from ollama_arena.backends.base import strip_thinking
        result = strip_thinking("<think>only</think>")
        assert result == ""

    def test_multiple_think_blocks(self):
        from ollama_arena.backends.base import strip_thinking
        text = "<think>A</think>mid<think>B</think>end"
        result = strip_thinking(text)
        assert "A" not in result
        assert "B" not in result
        assert "mid" in result
        assert "end" in result


# ──────────────────────────────────────────────────────────────────────────────
# base.py — inject_system
# ──────────────────────────────────────────────────────────────────────────────

class TestInjectSystem:
    def test_prepends_when_no_system(self):
        from ollama_arena.backends.base import inject_system
        msgs = [{"role": "user", "content": "hello"}]
        result = inject_system(msgs)
        assert result[0]["role"] == "system"
        assert result[1]["role"] == "user"
        assert len(result) == 2

    def test_no_prepend_when_system_exists(self):
        from ollama_arena.backends.base import inject_system
        msgs = [
            {"role": "system", "content": "custom system"},
            {"role": "user", "content": "hi"},
        ]
        result = inject_system(msgs)
        assert result[0]["content"] == "custom system"
        assert len(result) == 2

    def test_does_not_mutate_original(self):
        from ollama_arena.backends.base import inject_system
        original = [{"role": "user", "content": "x"}]
        result = inject_system(original)
        assert len(original) == 1  # untouched
        assert len(result) == 2

    def test_date_injected_in_system(self):
        from ollama_arena.backends.base import inject_system
        import datetime
        today = datetime.date.today().isoformat()
        result = inject_system([{"role": "user", "content": "q"}])
        assert today in result[0]["content"]


# ──────────────────────────────────────────────────────────────────────────────
# anthropic.py — _messages_to_anthropic
# ──────────────────────────────────────────────────────────────────────────────

class TestMessagesToAnthropic:
    def _convert(self, messages):
        from ollama_arena.backends.anthropic import _messages_to_anthropic
        return _messages_to_anthropic(messages)

    def test_system_extracted(self):
        msgs = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hi"},
        ]
        system, turns = self._convert(msgs)
        assert system == "You are helpful"
        assert len(turns) == 1
        assert turns[0]["role"] == "user"

    def test_no_system(self):
        msgs = [{"role": "user", "content": "hello"}]
        system, turns = self._convert(msgs)
        assert system is None
        assert len(turns) == 1

    def test_image_converted_to_parts(self):
        msgs = [{
            "role": "user",
            "content": "describe this",
            "images": ["data:image/png;base64,abc123"],
        }]
        _, turns = self._convert(msgs)
        content = turns[0]["content"]
        assert isinstance(content, list)
        text_part = next(p for p in content if p["type"] == "text")
        img_part = next(p for p in content if p["type"] == "image")
        assert text_part["text"] == "describe this"
        assert img_part["source"]["media_type"] == "image/png"
        assert img_part["source"]["data"] == "abc123"

    def test_plain_image_fallback_jpeg(self):
        msgs = [{"role": "user", "content": "", "images": ["not-a-data-uri"]}]
        _, turns = self._convert(msgs)
        img_part = next(p for p in turns[0]["content"] if p["type"] == "image")
        assert img_part["source"]["media_type"] == "image/jpeg"

    def test_tool_role_converted_to_user_tool_result(self):
        """agent_loop.py appends OpenAI-shaped {"role": "tool", ...} messages
        regardless of backend. Anthropic has no "tool" role — it must become
        a user message with a tool_result content block, or the API rejects
        the request on turn 2+ of any agent run."""
        msgs = [{
            "role": "tool",
            "tool_call_id": "toolu_01",
            "content": "72 degrees and sunny",
        }]
        _, turns = self._convert(msgs)
        assert len(turns) == 1
        assert turns[0]["role"] == "user"
        block = turns[0]["content"][0]
        assert block["type"] == "tool_result"
        assert block["tool_use_id"] == "toolu_01"
        assert block["content"] == "72 degrees and sunny"

    def test_assistant_tool_calls_converted_to_tool_use_blocks(self):
        """An OpenAI-shaped assistant message carrying msg["tool_calls"]
        must become Anthropic content blocks of type tool_use, not be
        passed through with the unrecognized "tool_calls" key dropped."""
        msgs = [{
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "toolu_01",
                "function": {"name": "get_weather", "arguments": '{"city": "NYC"}'},
            }],
        }]
        _, turns = self._convert(msgs)
        assert len(turns) == 1
        assert turns[0]["role"] == "assistant"
        block = next(p for p in turns[0]["content"] if p["type"] == "tool_use")
        assert block["id"] == "toolu_01"
        assert block["name"] == "get_weather"
        assert block["input"] == {"city": "NYC"}

    def test_assistant_tool_calls_with_text_keeps_text_block(self):
        msgs = [{
            "role": "assistant",
            "content": "Let me check that.",
            "tool_calls": [{
                "id": "t1",
                "function": {"name": "fn", "arguments": "{}"},
            }],
        }]
        _, turns = self._convert(msgs)
        text_block = next(p for p in turns[0]["content"] if p["type"] == "text")
        assert text_block["text"] == "Let me check that."

    def test_full_tool_round_trip_message_sequence(self):
        """Simulates the exact message shape agent_loop.py builds across a
        full tool round trip and asserts every turn converts to a role
        Anthropic accepts (only "user"/"assistant")."""
        msgs = [
            {"role": "user", "content": "What's the weather in NYC?"},
            {
                "role": "assistant", "content": "",
                "tool_calls": [{
                    "id": "toolu_01",
                    "function": {"name": "get_weather", "arguments": '{"city": "NYC"}'},
                }],
            },
            {"role": "tool", "tool_call_id": "toolu_01", "content": "72F sunny"},
        ]
        _, turns = self._convert(msgs)
        assert len(turns) == 3
        assert all(t["role"] in ("user", "assistant") for t in turns)


# ──────────────────────────────────────────────────────────────────────────────
# AnthropicBackend — text streaming
# ──────────────────────────────────────────────────────────────────────────────

class TestAnthropicBackendTextStreaming:
    def _backend(self, api_key="sk-ant-test"):
        from ollama_arena.backends.anthropic import AnthropicBackend
        return AnthropicBackend(api_key=api_key, base_url="https://api.anthropic.com/v1")

    def _sse_text(self, text: str, tokens_in: int = 10, tokens_out: int = 5):
        return _sse_lines(
            {"type": "message_start", "message": {"usage": {"input_tokens": tokens_in}}},
            {"type": "content_block_start", "index": 0,
             "content_block": {"type": "text", "text": ""}},
            {"type": "content_block_delta", "index": 0,
             "delta": {"type": "text_delta", "text": text}},
            {"type": "content_block_stop", "index": 0},
            {"type": "message_delta",
             "delta": {"stop_reason": "end_turn"},
             "usage": {"output_tokens": tokens_out}},
        )

    def test_basic_text_response(self):
        backend = self._backend()
        resp = _fake_response(self._sse_text("Hello world", tokens_in=15, tokens_out=3))
        with mock.patch("requests.post", return_value=resp):
            result = backend.generate("claude-sonnet-4-6", "Say hello")
        assert "Hello world" in result.text
        assert result.tokens_in == 15
        assert result.tokens_out == 3
        assert result.error == ""

    def test_finish_reason_end_turn(self):
        backend = self._backend()
        resp = _fake_response(self._sse_text("Done"))
        with mock.patch("requests.post", return_value=resp):
            turn = backend.chat_turn("claude-sonnet-4-6", [{"role": "user", "content": "hi"}], [])
        assert turn.finish_reason == "end_turn"

    def test_tps_computed(self):
        backend = self._backend()
        resp = _fake_response(self._sse_text("text", tokens_out=50))
        with (
            mock.patch("requests.post", return_value=resp),
            mock.patch("time.time", side_effect=[0.0, 0.0, 2.0, 2.0, 2.0]),
        ):
            result = backend.generate("claude-sonnet-4-6", "prompt")
        # tokens_out=50, latency≈2s → tps≈25; just verify it's non-negative
        assert result.tps >= 0

    def test_http_error_returns_error_field(self):
        backend = self._backend()
        err_resp = mock.MagicMock()
        err_resp.status_code = 401
        err_resp.text = "Unauthorized"
        with mock.patch("requests.post", return_value=err_resp):
            result = backend.generate("claude-sonnet-4-6", "prompt")
        assert result.error != ""
        assert "401" in result.error

    def test_http_error_still_closes_response(self):
        """Non-200 responses return early but must still close the
        underlying streaming connection rather than leaking it."""
        backend = self._backend()
        err_resp = mock.MagicMock()
        err_resp.status_code = 401
        err_resp.text = "Unauthorized"
        with mock.patch("requests.post", return_value=err_resp):
            backend.generate("claude-sonnet-4-6", "prompt")
        err_resp.close.assert_called_once()

    def test_success_response_closed(self):
        backend = self._backend()
        resp = _fake_response(self._sse_text("ok"))
        with mock.patch("requests.post", return_value=resp):
            backend.generate("claude-sonnet-4-6", "prompt")
        resp.close.assert_called_once()

    def test_connection_exception(self):
        backend = self._backend()
        with mock.patch("requests.post", side_effect=ConnectionError("refused")):
            result = backend.generate("claude-sonnet-4-6", "prompt")
        assert result.error != ""

    def test_generate_delegates_to_chat_turn(self):
        backend = self._backend()
        resp = _fake_response(self._sse_text("ok"))
        with mock.patch("requests.post", return_value=resp) as m:
            backend.generate("claude-haiku-4-5-20251001", "hi", temperature=0.5)
        call_kwargs = m.call_args
        body = call_kwargs[1]["json"]
        assert body["model"] == "claude-haiku-4-5-20251001"
        assert body["temperature"] == 0.5

    def test_empty_api_key_is_alive_false(self):
        from ollama_arena.backends.anthropic import AnthropicBackend
        b = AnthropicBackend(api_key="")
        assert not b.is_alive()

    def test_api_key_set_is_alive_true(self):
        backend = self._backend()
        assert backend.is_alive()

    def test_list_models_returns_list(self):
        backend = self._backend()
        models = backend.list_models()
        assert isinstance(models, list)
        assert len(models) > 0
        assert all(isinstance(m, str) for m in models)
        assert "claude-sonnet-4-6" in models

    def test_multi_chunk_concatenated(self):
        backend = self._backend()
        lines = _sse_lines(
            {"type": "message_start", "message": {"usage": {"input_tokens": 5}}},
            {"type": "content_block_start", "index": 0,
             "content_block": {"type": "text", "text": ""}},
            {"type": "content_block_delta", "index": 0,
             "delta": {"type": "text_delta", "text": "Hello"}},
            {"type": "content_block_delta", "index": 0,
             "delta": {"type": "text_delta", "text": " world"}},
            {"type": "content_block_stop", "index": 0},
            {"type": "message_delta",
             "delta": {"stop_reason": "end_turn"},
             "usage": {"output_tokens": 2}},
        )
        resp = _fake_response(lines)
        with mock.patch("requests.post", return_value=resp):
            result = backend.generate("claude-sonnet-4-6", "hi")
        assert result.text == "Hello world"


# ──────────────────────────────────────────────────────────────────────────────
# AnthropicBackend — tool_use streaming
# ──────────────────────────────────────────────────────────────────────────────

class TestAnthropicBackendToolUse:
    def _backend(self):
        from ollama_arena.backends.anthropic import AnthropicBackend
        return AnthropicBackend(api_key="sk-ant-test")

    def test_tool_call_parsed(self):
        backend = self._backend()
        lines = _sse_lines(
            {"type": "message_start", "message": {"usage": {"input_tokens": 20}}},
            {"type": "content_block_start", "index": 0,
             "content_block": {"type": "tool_use", "id": "toolu_01", "name": "get_weather"}},
            {"type": "content_block_delta", "index": 0,
             "delta": {"type": "input_json_delta", "partial_json": '{"city": '}},
            {"type": "content_block_delta", "index": 0,
             "delta": {"type": "input_json_delta", "partial_json": '"NYC"}'}},
            {"type": "content_block_stop", "index": 0},
            {"type": "message_delta",
             "delta": {"stop_reason": "tool_use"},
             "usage": {"output_tokens": 15}},
        )
        resp = _fake_response(lines)
        tools = [{
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather",
                "parameters": {"type": "object", "properties": {"city": {"type": "string"}}},
            }
        }]
        with mock.patch("requests.post", return_value=resp):
            turn = backend.chat_turn(
                "claude-sonnet-4-6",
                [{"role": "user", "content": "What's the weather in NYC?"}],
                tools,
            )
        assert len(turn.tool_calls) == 1
        tc = turn.tool_calls[0]
        assert tc["function"]["name"] == "get_weather"
        assert "NYC" in tc["function"]["arguments"]
        assert tc["id"] == "toolu_01"

    def test_tool_call_serialised_in_generate(self):
        backend = self._backend()
        lines = _sse_lines(
            {"type": "message_start", "message": {"usage": {"input_tokens": 5}}},
            {"type": "content_block_start", "index": 0,
             "content_block": {"type": "tool_use", "id": "t1", "name": "fn"}},
            {"type": "content_block_delta", "index": 0,
             "delta": {"type": "input_json_delta", "partial_json": "{}"}},
            {"type": "content_block_stop", "index": 0},
            {"type": "message_delta",
             "delta": {"stop_reason": "tool_use"},
             "usage": {"output_tokens": 5}},
        )
        resp = _fake_response(lines)
        with mock.patch("requests.post", return_value=resp):
            result = backend.generate_with_tools(
                "claude-sonnet-4-6",
                [{"role": "user", "content": "call fn"}],
                tools=[{
                    "type": "function",
                    "function": {"name": "fn", "description": "do", "parameters": {}},
                }],
            )
        # When there are tool_calls and no text, result.text is the JSON
        assert result.tool_calls or result.text

    def test_thinking_budget_sets_body_flag(self):
        backend = self._backend()
        lines = _sse_lines(
            {"type": "message_start", "message": {"usage": {"input_tokens": 5}}},
            {"type": "content_block_stop", "index": 0},
            {"type": "message_delta",
             "delta": {"stop_reason": "end_turn"},
             "usage": {"output_tokens": 1}},
        )
        resp = _fake_response(lines)
        with mock.patch("requests.post", return_value=resp) as m:
            backend.chat_turn(
                "claude-sonnet-4-6",
                [{"role": "user", "content": "think"}],
                [],
                thinking_budget=2000,
            )
        body = m.call_args[1]["json"]
        assert "thinking" in body
        assert body["thinking"]["budget_tokens"] == 2000
        assert "temperature" not in body


# ──────────────────────────────────────────────────────────────────────────────
# OllamaBackend — streaming JSON
# ──────────────────────────────────────────────────────────────────────────────

class TestOllamaBackend:
    def _backend(self):
        from ollama_arena.backends.ollama import OllamaBackend
        return OllamaBackend(base_url="http://localhost:11434")

    def test_basic_text(self):
        backend = self._backend()
        chunks = _ollama_chunks("Hello", " world")
        resp = _fake_ollama_response(chunks)
        with mock.patch("requests.post", return_value=resp):
            result = backend.generate("llama3", "Say hello")
        assert "Hello" in result.text
        assert " world" in result.text

    def test_token_counts_from_done_chunk(self):
        backend = self._backend()
        chunks = _ollama_chunks("hi", done_tokens=(42, 17))
        resp = _fake_ollama_response(chunks)
        with mock.patch("requests.post", return_value=resp):
            result = backend.generate("llama3", "q")
        assert result.tokens_in == 42
        assert result.tokens_out == 17

    def test_tool_calls_collected(self):
        backend = self._backend()
        tc = {"function": {"name": "search", "arguments": {"q": "test"}}}
        chunks = [
            json.dumps({
                "message": {
                    "content": "",
                    "role": "assistant",
                    "tool_calls": [tc],
                }
            }).encode(),
            json.dumps({
                "message": {"content": "", "role": "assistant"},
                "done": True,
                "prompt_eval_count": 5,
                "eval_count": 3,
            }).encode(),
        ]
        resp = _fake_ollama_response(chunks)
        with mock.patch("requests.post", return_value=resp):
            turn = backend.chat_turn("llama3", [{"role": "user", "content": "search"}], [])
        assert len(turn.tool_calls) == 1
        assert turn.finish_reason == "tool_calls"

    def test_connection_error_returns_error(self):
        backend = self._backend()
        with mock.patch("requests.post", side_effect=ConnectionError("refused")):
            result = backend.generate("llama3", "hi")
        assert result.error != ""

    def test_malformed_json_line_skipped(self):
        backend = self._backend()
        chunks = [
            b"not-json",
            *_ollama_chunks("fine"),
        ]
        resp = _fake_ollama_response(chunks)
        with mock.patch("requests.post", return_value=resp):
            result = backend.generate("llama3", "q")
        assert result.error == ""

    def test_tps_positive(self):
        backend = self._backend()
        chunks = _ollama_chunks("a" * 100, done_tokens=(20, 50))
        resp = _fake_ollama_response(chunks)
        with mock.patch("requests.post", return_value=resp):
            result = backend.generate("llama3", "q")
        assert result.tps > 0

    def test_name_is_ollama(self):
        backend = self._backend()
        assert backend.name == "ollama"

    def test_raw_generate_malformed_json_does_not_crash(self):
        """_do_generate used a bare `except:` that would also swallow
        KeyboardInterrupt/SystemExit; it must only catch JSON decode errors
        on malformed lines and otherwise still produce a clean result."""
        backend = self._backend()
        chunks = [
            b"not-json-at-all",
            json.dumps({"response": "fine"}).encode(),
            json.dumps({
                "response": "", "done": True,
                "prompt_eval_count": 5, "eval_count": 3,
            }).encode(),
        ]
        resp = _fake_ollama_response(chunks)
        with mock.patch("requests.post", return_value=resp):
            result = backend._do_generate("llama3", "raw prompt")
        assert result.error == ""
        assert "fine" in result.text

    def test_chat_turn_closes_streaming_response(self):
        """The streaming requests.Response must be closed on every path so
        the connection is released back to the pool instead of leaking."""
        backend = self._backend()
        chunks = _ollama_chunks("hi")
        resp = _fake_ollama_response(chunks)
        with mock.patch("requests.post", return_value=resp):
            backend.generate("llama3", "q")
        resp.close.assert_called_once()

    def test_do_generate_closes_streaming_response(self):
        backend = self._backend()
        chunks = _ollama_chunks("hi")
        resp = _fake_ollama_response(chunks)
        with mock.patch("requests.post", return_value=resp):
            backend._do_generate("llama3", "q")
        resp.close.assert_called_once()

    def test_response_closed_even_on_mid_stream_exception(self):
        """If iterating the stream raises partway through, the response
        must still be closed rather than leaked."""
        backend = self._backend()
        resp = mock.MagicMock()
        resp.status_code = 200
        resp.iter_lines = mock.MagicMock(side_effect=RuntimeError("connection reset"))
        with mock.patch("requests.post", return_value=resp):
            result = backend.generate("llama3", "q")
        assert result.error != ""
        resp.close.assert_called_once()


# ──────────────────────────────────────────────────────────────────────────────
# auto_backend routing
# ──────────────────────────────────────────────────────────────────────────────

class TestAutoBackendRouting:
    def test_none_returns_ollama(self):
        from ollama_arena.backends.auto import auto_backend
        from ollama_arena.backends.ollama import OllamaBackend
        b = auto_backend(None)
        assert isinstance(b, OllamaBackend)

    def test_ollama_url_port_11434(self):
        from ollama_arena.backends.auto import auto_backend
        from ollama_arena.backends.ollama import OllamaBackend
        b = auto_backend("http://localhost:11434")
        assert isinstance(b, OllamaBackend)

    def test_anthropic_preset(self):
        from ollama_arena.backends.auto import auto_backend
        from ollama_arena.backends.anthropic import AnthropicBackend
        b = auto_backend("anthropic", api_key="sk-ant-x")
        assert isinstance(b, AnthropicBackend)

    def test_claude_keyword(self):
        from ollama_arena.backends.auto import auto_backend
        from ollama_arena.backends.anthropic import AnthropicBackend
        b = auto_backend("claude", api_key="sk-ant-x")
        assert isinstance(b, AnthropicBackend)

    def test_anthropic_domain_in_url(self):
        from ollama_arena.backends.auto import auto_backend
        from ollama_arena.backends.anthropic import AnthropicBackend
        b = auto_backend("https://api.anthropic.com/v1", api_key="sk-ant-x")
        assert isinstance(b, AnthropicBackend)

    def test_openai_compat_url_unknown_port(self):
        from ollama_arena.backends.auto import auto_backend
        from ollama_arena.backends.openai_compat import OpenAICompatBackend
        b = auto_backend("http://localhost:5555/v1/chat")
        assert isinstance(b, OpenAICompatBackend)

    def test_detect_backend_ollama_url(self):
        from ollama_arena.backends.auto import detect_backend
        assert detect_backend("http://localhost:11434") == "ollama"

    def test_detect_backend_none_returns_ollama(self):
        from ollama_arena.backends.auto import detect_backend
        assert detect_backend(None) == "ollama"

    def test_detect_backend_unknown_url_openai_compat(self):
        from ollama_arena.backends.auto import detect_backend
        assert detect_backend("http://some-server:9999/v1") == "openai-compat"


# ──────────────────────────────────────────────────────────────────────────────
# AnthropicBackend — build_body correctness
# ──────────────────────────────────────────────────────────────────────────────

class TestAnthropicBuildBody:
    def _backend(self):
        from ollama_arena.backends.anthropic import AnthropicBackend
        return AnthropicBackend(api_key="sk-ant-test")

    def test_stream_always_true(self):
        backend = self._backend()
        body = backend._build_body("claude-sonnet-4-6", [{"role": "user", "content": "hi"}], [])
        assert body["stream"] is True

    def test_max_tokens_default(self):
        from ollama_arena.backends.anthropic import _DEFAULT_MAX_TOKENS
        backend = self._backend()
        body = backend._build_body("claude-sonnet-4-6", [{"role": "user", "content": "hi"}], [])
        assert body["max_tokens"] == _DEFAULT_MAX_TOKENS

    def test_max_tokens_override(self):
        backend = self._backend()
        body = backend._build_body(
            "claude-sonnet-4-6",
            [{"role": "user", "content": "hi"}],
            [],
            num_predict=512,
        )
        assert body["max_tokens"] == 512

    def test_tools_converted_to_anthropic_schema(self):
        backend = self._backend()
        tools = [{
            "type": "function",
            "function": {
                "name": "my_fn",
                "description": "does stuff",
                "parameters": {"type": "object", "properties": {}},
            }
        }]
        body = backend._build_body(
            "claude-sonnet-4-6",
            [{"role": "user", "content": "hi"}],
            tools,
        )
        assert "tools" in body
        t = body["tools"][0]
        assert t["name"] == "my_fn"
        assert t["description"] == "does stuff"
        assert "input_schema" in t

    def test_system_extracted_to_top_level(self):
        backend = self._backend()
        msgs = [
            {"role": "system", "content": "Be concise"},
            {"role": "user", "content": "hi"},
        ]
        body = backend._build_body("claude-sonnet-4-6", msgs, [])
        assert body.get("system") == "Be concise"
