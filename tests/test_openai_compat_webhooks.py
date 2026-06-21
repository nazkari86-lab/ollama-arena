"""Tests for OpenAICompatBackend and webhooks module."""
from __future__ import annotations

import json
import threading
import time
import unittest.mock as mock

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# Helpers shared with test_backends.py pattern
# ──────────────────────────────────────────────────────────────────────────────

def _oai_sse(*chunks: dict) -> list[str]:
    """Build OpenAI SSE lines (data: ... format) ending with [DONE]."""
    lines = []
    for chunk in chunks:
        lines.append(f"data: {json.dumps(chunk)}")
        lines.append("")
    lines.append("data: [DONE]")
    return lines


def _oai_delta(content: str = "", finish_reason: str | None = None,
               tool_calls: list | None = None) -> dict:
    delta: dict = {}
    if content:
        delta["content"] = content
    if tool_calls is not None:
        delta["tool_calls"] = tool_calls
    choice: dict = {"delta": delta}
    if finish_reason:
        choice["finish_reason"] = finish_reason
    return {"choices": [choice]}


def _fake_resp(lines: list[str], status: int = 200):
    r = mock.MagicMock()
    r.status_code = status
    r.text = ""
    r.iter_lines = mock.MagicMock(return_value=iter(lines))
    return r


# ──────────────────────────────────────────────────────────────────────────────
# prepare_messages_for_api
# ──────────────────────────────────────────────────────────────────────────────

class TestPrepareMessages:
    def test_plain_message_passthrough(self):
        from ollama_arena.backends.openai_compat import prepare_messages_for_api
        msgs = [{"role": "user", "content": "hello"}]
        result = prepare_messages_for_api(msgs)
        assert result[0]["content"] == "hello"

    def test_image_converted_to_parts(self):
        from ollama_arena.backends.openai_compat import prepare_messages_for_api
        msgs = [{"role": "user", "content": "look", "images": ["data:image/png;base64,abc"]}]
        result = prepare_messages_for_api(msgs)
        content = result[0]["content"]
        assert isinstance(content, list)
        types = [p["type"] for p in content]
        assert "text" in types
        assert "image_url" in types

    def test_image_url_data_uri_passed_through(self):
        from ollama_arena.backends.openai_compat import _image_url
        uri = "data:image/jpeg;base64,xyz"
        assert _image_url(uri) == uri

    def test_image_url_raw_base64_wrapped(self):
        from ollama_arena.backends.openai_compat import _image_url
        raw = "abc123"
        result = _image_url(raw)
        assert result.startswith("data:image/jpeg;base64,")
        assert "abc123" in result

    def test_images_key_stripped_from_output(self):
        from ollama_arena.backends.openai_compat import prepare_messages_for_api
        msgs = [{"role": "user", "content": "x", "images": ["data:image/png;base64,y"]}]
        result = prepare_messages_for_api(msgs)
        assert "images" not in result[0]


# ──────────────────────────────────────────────────────────────────────────────
# OpenAICompatBackend — init and presets
# ──────────────────────────────────────────────────────────────────────────────

class TestOpenAICompatInit:
    def _make(self, url="http://localhost:8000/v1", api_key=None):
        from ollama_arena.backends.openai_compat import OpenAICompatBackend
        return OpenAICompatBackend(base_url=url, api_key=api_key)

    def test_name_is_openai_compat(self):
        b = self._make()
        assert b.name == "openai-compat"

    def test_preset_vllm_resolves_url(self):
        from ollama_arena.backends.openai_compat import OpenAICompatBackend
        b = OpenAICompatBackend(base_url="vllm")
        assert "8000" in b.base

    def test_preset_lmstudio_resolves_url(self):
        from ollama_arena.backends.openai_compat import OpenAICompatBackend
        b = OpenAICompatBackend(base_url="lmstudio")
        assert "1234" in b.base

    def test_api_key_empty_falls_back_to_EMPTY(self):
        import os
        with mock.patch.dict(os.environ, {}, clear=False):
            b = self._make(api_key=None)
        assert b.api_key  # either env var or "EMPTY"

    def test_explicit_api_key_used(self):
        b = self._make(api_key="sk-test-key")
        assert b.api_key == "sk-test-key"

    def test_authorization_header_set(self):
        b = self._make(api_key="sk-xyz")
        assert b._headers["Authorization"] == "Bearer sk-xyz"

    def test_trailing_slash_stripped(self):
        b = self._make(url="http://localhost:8000/v1/")
        assert not b.base.endswith("/")


# ──────────────────────────────────────────────────────────────────────────────
# OpenAICompatBackend — text streaming
# ──────────────────────────────────────────────────────────────────────────────

class TestOpenAICompatText:
    def _backend(self):
        from ollama_arena.backends.openai_compat import OpenAICompatBackend
        return OpenAICompatBackend(base_url="http://localhost:8000/v1", api_key="EMPTY")

    def test_basic_text(self):
        b = self._backend()
        lines = _oai_sse(
            _oai_delta("Hello"),
            _oai_delta(" world", finish_reason="stop"),
        )
        with mock.patch("requests.post", return_value=_fake_resp(lines)):
            result = b.generate("mistral", "say hello")
        assert "Hello" in result.text
        assert "world" in result.text
        assert result.error == ""

    def test_finish_reason_passed_through(self):
        b = self._backend()
        lines = _oai_sse(_oai_delta("ok", finish_reason="stop"))
        with mock.patch("requests.post", return_value=_fake_resp(lines)):
            turn = b.chat_turn("mistral", [{"role": "user", "content": "hi"}], [])
        assert turn.finish_reason == "stop"

    def test_usage_tokens_parsed(self):
        b = self._backend()
        lines = _oai_sse(
            {"usage": {"prompt_tokens": 12, "completion_tokens": 8}, "choices": []},
            _oai_delta("text", finish_reason="stop"),
        )
        with mock.patch("requests.post", return_value=_fake_resp(lines)):
            result = b.generate("mistral", "q")
        assert result.tokens_in == 12
        assert result.tokens_out == 8

    def test_http_error_returns_error(self):
        b = self._backend()
        err = _fake_resp([], status=500)
        err.text = "Internal Server Error"
        with mock.patch("requests.post", return_value=err):
            result = b.generate("mistral", "q")
        assert result.error != ""

    def test_connection_error(self):
        b = self._backend()
        with mock.patch("requests.post", side_effect=ConnectionError("refused")):
            result = b.generate("mistral", "q")
        assert result.error != ""

    def test_malformed_json_line_skipped(self):
        b = self._backend()
        lines = ["data: {bad json}", *_oai_sse(_oai_delta("ok", finish_reason="stop"))]
        with mock.patch("requests.post", return_value=_fake_resp(lines)):
            result = b.generate("mistral", "q")
        assert result.error == ""

    def test_done_line_breaks_loop(self):
        b = self._backend()
        lines = _oai_sse(_oai_delta("first")) + ["data: should-not-appear"]
        with mock.patch("requests.post", return_value=_fake_resp(lines)):
            result = b.generate("mistral", "q")
        assert "should-not-appear" not in result.text

    def test_stream_flag_in_body(self):
        b = self._backend()
        lines = _oai_sse(_oai_delta("ok"))
        with mock.patch("requests.post", return_value=_fake_resp(lines)) as m:
            b.generate("mistral", "hi")
        body = m.call_args[1]["json"]
        assert body["stream"] is True

    def test_success_response_closed(self):
        """The streaming requests.Response must be closed once consumed so
        the connection is released back to the pool instead of leaking."""
        b = self._backend()
        lines = _oai_sse(_oai_delta("ok", finish_reason="stop"))
        resp = _fake_resp(lines)
        with mock.patch("requests.post", return_value=resp):
            b.generate("mistral", "hi")
        resp.close.assert_called_once()

    def test_http_error_response_still_closed(self):
        """Non-200 responses return early but must still close the
        underlying streaming connection rather than leaking it."""
        b = self._backend()
        err = _fake_resp([], status=500)
        err.text = "Internal Server Error"
        with mock.patch("requests.post", return_value=err):
            b.generate("mistral", "q")
        err.close.assert_called_once()


# ──────────────────────────────────────────────────────────────────────────────
# OpenAICompatBackend — tool_calls streaming
# ──────────────────────────────────────────────────────────────────────────────

class TestOpenAICompatToolCalls:
    def _backend(self):
        from ollama_arena.backends.openai_compat import OpenAICompatBackend
        return OpenAICompatBackend(base_url="http://localhost:8000/v1", api_key="EMPTY")

    def test_tool_call_parsed(self):
        b = self._backend()
        lines = _oai_sse(
            _oai_delta(tool_calls=[{
                "index": 0,
                "id": "call_abc",
                "function": {"name": "search", "arguments": '{"q": "test"}'},
            }], finish_reason="tool_calls"),
        )
        with mock.patch("requests.post", return_value=_fake_resp(lines)):
            turn = b.chat_turn("mistral", [{"role": "user", "content": "search"}],
                               tools=[{"type": "function", "function": {"name": "search"}}])
        assert len(turn.tool_calls) == 1
        assert turn.tool_calls[0]["function"]["name"] == "search"
        assert turn.tool_calls[0]["id"] == "call_abc"

    def test_incremental_arguments_concatenated(self):
        b = self._backend()
        lines = _oai_sse(
            _oai_delta(tool_calls=[{
                "index": 0, "id": "c1",
                "function": {"name": "fn", "arguments": '{"x":'},
            }]),
            _oai_delta(tool_calls=[{
                "index": 0,
                "function": {"arguments": '"val"}'},
            }], finish_reason="tool_calls"),
        )
        with mock.patch("requests.post", return_value=_fake_resp(lines)):
            turn = b.chat_turn("mistral", [{"role": "user", "content": "go"}], [])
        args = turn.tool_calls[0]["function"]["arguments"]
        assert '"x"' in args
        assert '"val"' in args


# ──────────────────────────────────────────────────────────────────────────────
# OpenAICompatBackend — list_models
# ──────────────────────────────────────────────────────────────────────────────

class TestOpenAICompatListModels:
    def _backend(self):
        from ollama_arena.backends.openai_compat import OpenAICompatBackend
        return OpenAICompatBackend(base_url="http://localhost:8000/v1", api_key="EMPTY")

    def test_list_models_returns_list(self):
        b = self._backend()
        payload = {"data": [{"id": "mistral-7b"}, {"id": "llama-3-8b"}]}
        r = mock.MagicMock()
        r.ok = True
        r.json = mock.MagicMock(return_value=payload)
        with mock.patch("requests.get", return_value=r):
            models = b.list_models()
        assert "mistral-7b" in models
        assert "llama-3-8b" in models

    def test_list_models_error_returns_fallback(self):
        b = self._backend()
        with mock.patch("requests.get", side_effect=Exception("refused")):
            models = b.list_models()
        assert isinstance(models, list)

    def test_is_alive_success(self):
        b = self._backend()
        r = mock.MagicMock()
        r.status_code = 200
        with mock.patch("requests.get", return_value=r):
            assert b.is_alive()

    def test_is_alive_failure(self):
        b = self._backend()
        with mock.patch("requests.get", side_effect=Exception("down")):
            assert not b.is_alive()

    def test_is_alive_500_returns_false(self):
        b = self._backend()
        r = mock.MagicMock()
        r.status_code = 500
        with mock.patch("requests.get", return_value=r):
            assert not b.is_alive()


# ──────────────────────────────────────────────────────────────────────────────
# webhooks.py — _build_payload
# ──────────────────────────────────────────────────────────────────────────────

class TestBuildPayload:
    def _data(self, **kw):
        base = {
            "model_a": "llama3", "model_b": "phi3",
            "category": "code", "score_a": 3.0, "score_b": 2.0,
            "winner": "llama3",
            "elo_delta_a": 12.5, "elo_delta_b": -12.5,
            "duration_s": 4.2,
        }
        base.update(kw)
        return base

    def test_generic_payload_structure(self):
        import ollama_arena.webhooks as wh
        with mock.patch.object(wh, "_WEBHOOK_URL", "http://generic.example.com/hook"):
            payload = wh._build_payload("match_complete", self._data())
        assert payload["event"] == "match_complete"
        assert "data" in payload
        assert "ts" in payload

    def test_discord_payload_has_embeds(self):
        import ollama_arena.webhooks as wh
        url = "https://discord.com/api/webhooks/123/abc"
        with mock.patch.object(wh, "_WEBHOOK_URL", url):
            payload = wh._build_payload("match_complete", self._data())
        assert "embeds" in payload
        embed = payload["embeds"][0]
        assert "llama3" in embed["title"]
        assert "phi3" in embed["title"]
        assert embed["color"] == 0x57F287  # winner → green

    def test_discord_draw_color(self):
        import ollama_arena.webhooks as wh
        url = "https://discord.com/api/webhooks/123/abc"
        with mock.patch.object(wh, "_WEBHOOK_URL", url):
            payload = wh._build_payload("match_complete", self._data(winner="draw"))
        assert payload["embeds"][0]["color"] == 0x5865F2

    def test_slack_payload_has_text(self):
        import ollama_arena.webhooks as wh
        url = "https://hooks.slack.com/services/X/Y/Z"
        with mock.patch.object(wh, "_WEBHOOK_URL", url):
            payload = wh._build_payload("match_complete", self._data())
        assert "text" in payload
        assert "llama3" in payload["text"]
        assert "phi3" in payload["text"]

    def test_slack_text_has_score(self):
        import ollama_arena.webhooks as wh
        url = "https://hooks.slack.com/services/X/Y/Z"
        with mock.patch.object(wh, "_WEBHOOK_URL", url):
            payload = wh._build_payload("match_complete", self._data())
        assert "3.0" in payload["text"] or "3" in payload["text"]


# ──────────────────────────────────────────────────────────────────────────────
# webhooks.py — notify_match (fire-and-forget)
# ──────────────────────────────────────────────────────────────────────────────

class TestNotifyMatch:
    def _call(self, **kw):
        from ollama_arena.webhooks import notify_match
        defaults = dict(
            model_a="llama3", model_b="phi3", category="code",
            score_a=3.0, score_b=2.0,
            elo_a_before=1200.0, elo_a_after=1212.5,
            elo_b_before=1200.0, elo_b_after=1187.5,
            duration_s=3.7,
        )
        defaults.update(kw)
        notify_match(**defaults)

    def test_no_url_no_request(self):
        import ollama_arena.webhooks as wh
        with (
            mock.patch.object(wh, "_WEBHOOK_URL", ""),
            mock.patch.object(wh, "_SESSION", None),
            mock.patch("requests.Session") as sess_cls,
        ):
            self._call()
        sess_cls.assert_not_called()

    def test_with_url_spawns_thread(self):
        import ollama_arena.webhooks as wh
        fake_sess = mock.MagicMock()
        fake_resp = mock.MagicMock()
        fake_resp.status_code = 200
        fake_sess.post.return_value = fake_resp

        threads_started: list[threading.Thread] = []
        original_start = threading.Thread.start

        def _track_start(self_thread, *a, **kw):
            threads_started.append(self_thread)
            # Run synchronously in test to avoid timing issues
            self_thread._target(*self_thread._args)

        with (
            mock.patch.object(wh, "_WEBHOOK_URL", "http://example.com/hook"),
            mock.patch.object(wh, "_SESSION", fake_sess),
            mock.patch.object(threading.Thread, "start", _track_start),
        ):
            self._call()

        assert len(threads_started) == 1
        fake_sess.post.assert_called_once()

    def test_winner_determined_a_wins(self):
        import ollama_arena.webhooks as wh
        fake_sess = mock.MagicMock()
        fake_sess.post.return_value.status_code = 200
        captured: list[dict] = []

        original_post = wh._post
        def _capture(url, payload):
            captured.append(payload)

        with (
            mock.patch.object(wh, "_WEBHOOK_URL", "http://example.com/hook"),
            mock.patch.object(wh, "_SESSION", fake_sess),
            mock.patch.object(wh, "_post", _capture),
            mock.patch.object(threading.Thread, "start",
                              lambda t, *a, **kw: t._target(*t._args)),
        ):
            self._call(score_a=3.0, score_b=1.0)

        assert len(captured) == 1
        assert captured[0]["data"]["winner"] == "llama3"

    def test_winner_determined_b_wins(self):
        import ollama_arena.webhooks as wh
        captured: list[dict] = []

        def _capture(url, payload):
            captured.append(payload)

        with (
            mock.patch.object(wh, "_WEBHOOK_URL", "http://example.com/hook"),
            mock.patch.object(wh, "_post", _capture),
            mock.patch.object(threading.Thread, "start",
                              lambda t, *a, **kw: t._target(*t._args)),
        ):
            self._call(score_a=1.0, score_b=3.0)

        assert captured[0]["data"]["winner"] == "phi3"

    def test_draw_detected(self):
        import ollama_arena.webhooks as wh
        captured: list[dict] = []

        def _capture(url, payload):
            captured.append(payload)

        with (
            mock.patch.object(wh, "_WEBHOOK_URL", "http://example.com/hook"),
            mock.patch.object(wh, "_post", _capture),
            mock.patch.object(threading.Thread, "start",
                              lambda t, *a, **kw: t._target(*t._args)),
        ):
            self._call(score_a=2.0, score_b=2.0)

        assert captured[0]["data"]["winner"] == "draw"

    def test_elo_delta_computed(self):
        import ollama_arena.webhooks as wh
        captured: list[dict] = []

        def _capture(url, payload):
            captured.append(payload)

        with (
            mock.patch.object(wh, "_WEBHOOK_URL", "http://example.com/hook"),
            mock.patch.object(wh, "_post", _capture),
            mock.patch.object(threading.Thread, "start",
                              lambda t, *a, **kw: t._target(*t._args)),
        ):
            self._call(
                elo_a_before=1200.0, elo_a_after=1215.0,
                elo_b_before=1200.0, elo_b_after=1185.0,
            )

        data = captured[0]["data"]
        assert data["elo_delta_a"] == pytest.approx(15.0, abs=0.2)
        assert data["elo_delta_b"] == pytest.approx(-15.0, abs=0.2)


# ──────────────────────────────────────────────────────────────────────────────
# webhooks.py — _post error handling
# ──────────────────────────────────────────────────────────────────────────────

class TestPostFunction:
    def test_4xx_response_logged(self, caplog):
        import ollama_arena.webhooks as wh
        import logging
        fake_sess = mock.MagicMock()
        r = mock.MagicMock()
        r.status_code = 403
        r.text = "Forbidden"
        fake_sess.post.return_value = r

        with (
            mock.patch.object(wh, "_SESSION", fake_sess),
            caplog.at_level(logging.WARNING, logger="arena.webhooks"),
        ):
            wh._post("http://example.com", {"event": "test"})

        assert any("403" in rec.message for rec in caplog.records)

    def test_exception_logged_not_raised(self, caplog):
        import ollama_arena.webhooks as wh
        import logging
        fake_sess = mock.MagicMock()
        fake_sess.post.side_effect = ConnectionError("refused")

        with (
            mock.patch.object(wh, "_SESSION", fake_sess),
            caplog.at_level(logging.WARNING, logger="arena.webhooks"),
        ):
            wh._post("http://example.com", {"event": "test"})  # must not raise

        assert any("Webhook POST failed" in rec.message for rec in caplog.records)

    def test_no_session_returns_silently(self):
        import ollama_arena.webhooks as wh
        with mock.patch.object(wh, "_SESSION", None):
            with mock.patch("ollama_arena.webhooks._session", return_value=None):
                wh._post("http://x.com", {})  # must not raise


# ──────────────────────────────────────────────────────────────────────────────
# webhooks.py — secret-leakage prevention (_post must never log the raw
# webhook URL: Discord/Slack webhook URLs embed a bearer-equivalent secret
# token directly in the path, e.g. /api/webhooks/<id>/<token>).
# ──────────────────────────────────────────────────────────────────────────────

class TestWebhookSecretRedaction:
    SECRET_URL = "https://discord.com/api/webhooks/123456/TOTALLY_SECRET_TOKEN_ABC"

    def test_4xx_response_does_not_leak_token_in_log(self, caplog):
        import ollama_arena.webhooks as wh
        import logging
        fake_sess = mock.MagicMock()
        r = mock.MagicMock()
        r.status_code = 403
        r.text = "Forbidden"
        fake_sess.post.return_value = r

        with (
            mock.patch.object(wh, "_SESSION", fake_sess),
            caplog.at_level(logging.WARNING, logger="arena.webhooks"),
        ):
            wh._post(self.SECRET_URL, {"event": "test"})

        assert not any("TOTALLY_SECRET_TOKEN_ABC" in rec.message for rec in caplog.records)
        # The 403 is still observable, just without the secret path.
        assert any("403" in rec.message for rec in caplog.records)

    def test_exception_message_does_not_leak_token_in_log(self, caplog):
        """requests/urllib3 ConnectionError messages often embed the full
        request URL (including the secret token) in their str() — the
        warning log must not interpolate the exception object directly."""
        import ollama_arena.webhooks as wh
        import logging
        fake_sess = mock.MagicMock()
        # Simulate a requests-style error whose message embeds the full URL.
        fake_sess.post.side_effect = ConnectionError(
            f"HTTPSConnectionPool(host='discord.com'): Max retries exceeded "
            f"with url: {self.SECRET_URL.replace('https://discord.com', '')} "
            f"(refused)"
        )

        with (
            mock.patch.object(wh, "_SESSION", fake_sess),
            caplog.at_level(logging.WARNING, logger="arena.webhooks"),
        ):
            wh._post(self.SECRET_URL, {"event": "test"})  # must not raise

        assert not any("TOTALLY_SECRET_TOKEN_ABC" in rec.message for rec in caplog.records)
        assert any("Webhook POST failed" in rec.message for rec in caplog.records)

    def test_redact_url_strips_path_and_query(self):
        import ollama_arena.webhooks as wh
        redacted = wh._redact_url("https://hooks.slack.com/services/T0/B0/SECRETTOKEN?x=1")
        assert "SECRETTOKEN" not in redacted
        assert redacted == "https://hooks.slack.com/***"

    def test_redact_url_handles_garbage_input(self):
        import ollama_arena.webhooks as wh
        # Must never raise, even on malformed input.
        result = wh._redact_url("not a url at all :::")
        assert isinstance(result, str)
