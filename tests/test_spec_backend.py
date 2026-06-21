"""Tests for backends/spec.py — SpeculativeBackend, SpecManager, and helper functions."""
from __future__ import annotations

import json
import subprocess
import unittest.mock as mock

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# Pure helpers
# ──────────────────────────────────────────────────────────────────────────────

class TestHelpers:
    def test_is_spec_model_true(self):
        from ollama_arena.backends.spec import is_spec_model
        assert is_spec_model("spec:qwen3-14b") is True

    def test_is_spec_model_false(self):
        from ollama_arena.backends.spec import is_spec_model
        assert is_spec_model("llama3:8b") is False

    def test_is_spec_model_empty(self):
        from ollama_arena.backends.spec import is_spec_model
        assert is_spec_model("") is False

    def test_spec_name_from_port_known(self):
        from ollama_arena.backends.spec import spec_name_from_port
        name = spec_name_from_port(8888)
        assert name == "spec:qwen3-14b"

    def test_spec_name_from_port_unknown(self):
        from ollama_arena.backends.spec import spec_name_from_port
        assert spec_name_from_port(9999) is None

    def test_spec_servers_not_empty(self):
        from ollama_arena.backends.spec import SPEC_SERVERS
        assert len(SPEC_SERVERS) > 0

    def test_spec_servers_have_required_keys(self):
        from ollama_arena.backends.spec import SPEC_SERVERS
        for name, cfg in SPEC_SERVERS.items():
            assert "port" in cfg
            assert "main" in cfg
            assert "draft" in cfg
            assert "ctx" in cfg


# ──────────────────────────────────────────────────────────────────────────────
# SpeculativeBackend — init and pure methods
# ──────────────────────────────────────────────────────────────────────────────

class TestSpeculativeBackendInit:
    def _make(self, spec_name="spec:qwen3-14b"):
        from ollama_arena.backends.spec import SpeculativeBackend
        return SpeculativeBackend(spec_name)

    def test_init_valid_name(self):
        b = self._make()
        assert b.spec_name == "spec:qwen3-14b"

    def test_init_sets_port(self):
        b = self._make()
        assert b.port == 8888

    def test_init_invalid_name_raises(self):
        from ollama_arena.backends.spec import SpeculativeBackend
        with pytest.raises(ValueError, match="Unknown spec server"):
            SpeculativeBackend("spec:nonexistent")

    def test_init_base_url(self):
        b = self._make()
        assert "8888" in b.base
        assert "localhost" in b.base

    def test_name_attribute(self):
        from ollama_arena.backends.spec import SpeculativeBackend
        assert SpeculativeBackend.name == "speculative"

    def test_timeout_default(self):
        b = self._make()
        assert b.timeout == 300

    def test_timeout_custom(self):
        from ollama_arena.backends.spec import SpeculativeBackend
        b = SpeculativeBackend("spec:qwen3-14b", timeout=60)
        assert b.timeout == 60


# ──────────────────────────────────────────────────────────────────────────────
# SpeculativeBackend — is_alive, _get_model_id, health
# ──────────────────────────────────────────────────────────────────────────────

class TestSpeculativeBackendMethods:
    def _make(self):
        from ollama_arena.backends.spec import SpeculativeBackend
        return SpeculativeBackend("spec:qwen3-14b")

    def test_is_alive_true_when_200(self):
        b = self._make()
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        with mock.patch("requests.get", return_value=mock_resp):
            assert b.is_alive() is True

    def test_is_alive_false_when_non_200(self):
        b = self._make()
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 503
        with mock.patch("requests.get", return_value=mock_resp):
            assert b.is_alive() is False

    def test_is_alive_false_on_exception(self):
        b = self._make()
        with mock.patch("requests.get", side_effect=Exception("connection refused")):
            assert b.is_alive() is False

    def test_get_model_id_cached(self):
        b = self._make()
        b._model_id = "cached-model"
        result = b._get_model_id()
        assert result == "cached-model"

    def test_get_model_id_from_api(self):
        b = self._make()
        mock_resp = mock.MagicMock()
        mock_resp.json.return_value = {"data": [{"id": "qwen3-14b-api"}]}
        with mock.patch("requests.get", return_value=mock_resp):
            result = b._get_model_id()
        assert result == "qwen3-14b-api"

    def test_get_model_id_fallback_on_exception(self):
        b = self._make()
        with mock.patch("requests.get", side_effect=Exception("fail")):
            result = b._get_model_id()
        assert result == b.cfg["main"]

    def test_get_model_id_fallback_empty_data(self):
        b = self._make()
        mock_resp = mock.MagicMock()
        mock_resp.json.return_value = {"data": []}
        with mock.patch("requests.get", return_value=mock_resp):
            result = b._get_model_id()
        assert result == b.cfg["main"]

    def test_list_models_when_alive(self):
        b = self._make()
        with mock.patch.object(b, "is_alive", return_value=True):
            result = b.list_models()
        assert result == ["spec:qwen3-14b"]

    def test_list_models_when_not_alive(self):
        b = self._make()
        with mock.patch.object(b, "is_alive", return_value=False):
            result = b.list_models()
        assert result == []

    def test_health_returns_dict(self):
        b = self._make()
        with mock.patch.object(b, "is_alive", return_value=False):
            result = b.health()
        assert isinstance(result, dict)
        assert result["name"] == "spec:qwen3-14b"
        assert result["running"] is False

    def test_health_includes_model_id_when_alive(self):
        b = self._make()
        with mock.patch.object(b, "is_alive", return_value=True):
            with mock.patch.object(b, "_get_model_id", return_value="qwen3-model"):
                result = b.health()
        assert result["model_id"] == "qwen3-model"

    def test_health_model_id_none_when_not_alive(self):
        b = self._make()
        with mock.patch.object(b, "is_alive", return_value=False):
            result = b.health()
        assert result["model_id"] is None


# ──────────────────────────────────────────────────────────────────────────────
# SpeculativeBackend — chat_turn with mocked streaming
# ──────────────────────────────────────────────────────────────────────────────

def _make_sse_lines(chunks: list[dict], include_done=True) -> list[str]:
    lines = [f"data: {json.dumps(c)}" for c in chunks]
    if include_done:
        lines.append("data: [DONE]")
    return lines


class TestSpeculativeBackendChatTurn:
    def _make(self):
        from ollama_arena.backends.spec import SpeculativeBackend
        return SpeculativeBackend("spec:qwen3-14b")

    def test_chat_turn_error_on_non_200(self):
        b = self._make()
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 503
        mock_resp.text = "Service Unavailable"
        with mock.patch.object(b, "_get_model_id", return_value="qwen3"):
            with mock.patch("requests.post", return_value=mock_resp):
                result = b.chat_turn("spec:qwen3-14b", [{"role": "user", "content": "hi"}], [])
        assert result.error is not None

    def test_chat_turn_error_on_exception(self):
        b = self._make()
        with mock.patch.object(b, "_get_model_id", return_value="qwen3"):
            with mock.patch("requests.post", side_effect=Exception("connection refused")):
                result = b.chat_turn("spec:qwen3-14b", [{"role": "user", "content": "hi"}], [])
        assert result.error is not None

    def test_chat_turn_success_basic(self):
        b = self._make()
        chunks = [
            {"choices": [{"delta": {"content": "Hello"}, "finish_reason": None}], "usage": None},
            {"choices": [{"delta": {"content": " world"}, "finish_reason": "stop"}], "usage": None},
            {"usage": {"prompt_tokens": 10, "completion_tokens": 20}},
        ]
        lines = _make_sse_lines(chunks)
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = iter(lines)
        with mock.patch.object(b, "_get_model_id", return_value="qwen3"):
            with mock.patch("requests.post", return_value=mock_resp):
                result = b.chat_turn("spec:qwen3-14b", [{"role": "user", "content": "hi"}], [])
        assert "Hello" in result.text or "world" in result.text

    def test_chat_turn_invalid_json_skipped(self):
        b = self._make()
        lines = ["data: {bad json}", "data: [DONE]"]
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = iter(lines)
        with mock.patch.object(b, "_get_model_id", return_value="qwen3"):
            with mock.patch("requests.post", return_value=mock_resp):
                result = b.chat_turn("spec:qwen3-14b", [{"role": "user", "content": "hi"}], [])
        assert not result.error or result.error == ""

    def test_chat_turn_non_data_lines_skipped(self):
        b = self._make()
        lines = ["", "event: ping", "data: [DONE]"]
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = iter(lines)
        with mock.patch.object(b, "_get_model_id", return_value="qwen3"):
            with mock.patch("requests.post", return_value=mock_resp):
                result = b.chat_turn("spec:qwen3-14b", [{"role": "user", "content": "hi"}], [])
        assert not result.error or result.error == ""

    def test_chat_turn_empty_choices_skipped(self):
        b = self._make()
        chunks = [{"choices": [], "usage": None}, {"choices": None, "usage": None}]
        lines = _make_sse_lines(chunks)
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = iter(lines)
        with mock.patch.object(b, "_get_model_id", return_value="qwen3"):
            with mock.patch("requests.post", return_value=mock_resp):
                result = b.chat_turn("spec:qwen3-14b", [{"role": "user", "content": "hi"}], [])
        assert result.text == ""


# ──────────────────────────────────────────────────────────────────────────────
# SpeculativeBackend — generate and generate_with_tools
# ──────────────────────────────────────────────────────────────────────────────

class TestSpeculativeBackendGenerate:
    def _make(self):
        from ollama_arena.backends.spec import SpeculativeBackend
        return SpeculativeBackend("spec:qwen3-14b")

    def _mock_chat_turn_ok(self, text="Response text", tokens_out=10, latency=0.5):
        from ollama_arena.backends.base import ChatTurnResult
        return ChatTurnResult(
            text=text, tokens_out=tokens_out, latency_s=latency,
            time_to_first=0.1, finish_reason="stop"
        )

    def _mock_chat_turn_error(self):
        from ollama_arena.backends.base import ChatTurnResult
        return ChatTurnResult(error="Something failed", latency_s=0.1)

    def test_generate_returns_gen_result(self):
        from ollama_arena.backends.base import GenResult
        b = self._make()
        with mock.patch.object(b, "chat_turn", return_value=self._mock_chat_turn_ok()):
            result = b.generate("spec:qwen3-14b", "Hello")
        assert isinstance(result, GenResult)

    def test_generate_with_tools_success(self):
        from ollama_arena.backends.base import GenResult
        b = self._make()
        with mock.patch.object(b, "chat_turn", return_value=self._mock_chat_turn_ok()):
            result = b.generate_with_tools("spec:qwen3-14b", [{"role": "user", "content": "hi"}], [])
        assert isinstance(result, GenResult)
        assert result.text == "Response text"

    def test_generate_with_tools_error(self):
        from ollama_arena.backends.base import GenResult
        b = self._make()
        with mock.patch.object(b, "chat_turn", return_value=self._mock_chat_turn_error()):
            result = b.generate_with_tools("spec:qwen3-14b", [{"role": "user", "content": "hi"}], [])
        assert isinstance(result, GenResult)
        assert result.error is not None

    def test_generate_with_tools_tps_calculated(self):
        b = self._make()
        with mock.patch.object(b, "chat_turn", return_value=self._mock_chat_turn_ok("Hello", 100, 2.0)):
            result = b.generate_with_tools("spec:qwen3-14b", [{"role": "user", "content": "hi"}], [])
        assert result.tps > 0

    def test_generate_with_tools_tool_calls_as_text(self):
        from ollama_arena.backends.base import ChatTurnResult
        b = self._make()
        turn = ChatTurnResult(
            text="",
            tool_calls=[{"function": {"name": "my_tool", "arguments": "{}"}}],
            tokens_out=5,
            latency_s=0.3,
        )
        with mock.patch.object(b, "chat_turn", return_value=turn):
            result = b.generate_with_tools("spec:qwen3-14b", [{"role": "user", "content": "hi"}], [])
        assert "my_tool" in result.text


# ──────────────────────────────────────────────────────────────────────────────
# SpecManager
# ──────────────────────────────────────────────────────────────────────────────

class TestSpecManager:
    def _make(self):
        from ollama_arena.backends.spec import SpecManager
        return SpecManager()

    def test_init_does_not_crash(self):
        sm = self._make()
        assert sm is not None

    def test_procs_initially_empty(self):
        sm = self._make()
        assert sm._procs == {}

    def test_status_returns_list_of_all_servers(self):
        from ollama_arena.backends.spec import SPEC_SERVERS
        sm = self._make()
        with mock.patch.object(sm, "_is_port_open", return_value=False):
            result = sm.status()
        assert len(result) == len(SPEC_SERVERS)

    def test_status_has_required_keys(self):
        sm = self._make()
        with mock.patch.object(sm, "_is_port_open", return_value=False):
            result = sm.status()
        entry = result[0]
        assert "name" in entry
        assert "port" in entry
        assert "running" in entry

    def test_status_running_true_when_port_open(self):
        sm = self._make()
        with mock.patch.object(sm, "_is_port_open", return_value=True):
            result = sm.status()
        assert all(e["running"] is True for e in result)

    def test_start_unknown_returns_error(self):
        sm = self._make()
        result = sm.start("spec:nonexistent")
        assert result["ok"] is False

    def test_start_already_running_returns_ok(self):
        sm = self._make()
        with mock.patch.object(sm, "_is_port_open", return_value=True):
            result = sm.start("spec:qwen3-14b")
        assert result["ok"] is True
        assert "already running" in result["message"]

    def test_start_script_not_found_returns_error(self):
        sm = self._make()
        with mock.patch.object(sm, "_is_port_open", return_value=False):
            with mock.patch("ollama_arena.backends.spec.Path") as mock_path:
                mock_path.return_value.exists.return_value = False
                mock_path.home.return_value = mock.MagicMock()
                result = sm.start("spec:qwen3-14b")
        assert result["ok"] is False

    def test_start_already_in_progress_refused(self):
        """A second start() call for the same name while the first is still
        mid-start (e.g. waiting for the port to open) must be refused
        instead of spawning a duplicate llama-server process."""
        sm = self._make()
        sm._starting.add("spec:qwen3-14b")
        with mock.patch.object(sm, "_is_port_open", return_value=False):
            result = sm.start("spec:qwen3-14b")
        assert result["ok"] is False
        assert "already starting" in result["error"]

    def test_start_refuses_beyond_concurrency_cap(self):
        """Starting a server beyond MAX_CONCURRENT_SPEC_SERVERS must be
        refused — this is the guard against the GPU/swap incident where
        all 8 registered servers were started at once."""
        from ollama_arena.backends.spec import SPEC_SERVERS, MAX_CONCURRENT_SPEC_SERVERS
        sm = self._make()
        already_running = list(SPEC_SERVERS)[:MAX_CONCURRENT_SPEC_SERVERS]
        target = list(SPEC_SERVERS)[MAX_CONCURRENT_SPEC_SERVERS]

        def _fake_port_open(port):
            running_ports = {SPEC_SERVERS[n]["port"] for n in already_running}
            return port in running_ports

        with mock.patch.object(sm, "_is_port_open", side_effect=_fake_port_open):
            result = sm.start(target)
        assert result["ok"] is False
        assert "Refusing to start" in result["error"]

    def test_start_within_cap_proceeds_to_script_check(self):
        """Starting a server when under the concurrency cap should not be
        blocked by the cap itself (it can still fail later for other
        reasons, e.g. missing script, but not because of the cap)."""
        from ollama_arena.backends.spec import SPEC_SERVERS, MAX_CONCURRENT_SPEC_SERVERS
        sm = self._make()
        assert MAX_CONCURRENT_SPEC_SERVERS < len(SPEC_SERVERS)
        target = next(iter(SPEC_SERVERS))
        with mock.patch.object(sm, "_is_port_open", return_value=False):
            with mock.patch("ollama_arena.backends.spec.Path") as mock_path:
                mock_path.return_value.exists.return_value = False
                result = sm.start(target)
        # Falls through to the "script not found" branch, not the cap.
        assert result["ok"] is False
        assert "Script not found" in result["error"]

    def test_stop_unknown_returns_error(self):
        sm = self._make()
        result = sm.stop("spec:nonexistent")
        assert result["ok"] is False

    def test_stop_sends_sigterm_before_sigkill(self):
        """Port-based kill must try SIGTERM (-15) first; only send SIGKILL
        (-9) if the process is still occupying the port afterward."""
        sm = self._make()
        calls = []

        def _fake_run(cmd, **kwargs):
            calls.append(cmd)
            result = mock.MagicMock()
            if cmd[0] == "lsof":
                result.stdout = "4242\n"
            return result

        # Port stays open through the whole grace-period wait, forcing the
        # SIGKILL escalation path. time.sleep is mocked so the 10-iteration
        # wait loop doesn't actually pause the test.
        with mock.patch("subprocess.run", side_effect=_fake_run), \
             mock.patch.object(sm, "_is_port_open", return_value=True), \
             mock.patch("time.sleep"):
            sm.stop("spec:qwen3-14b")

        kill_calls = [c for c in calls if c[0] == "kill"]
        assert ["kill", "-15", "4242"] in kill_calls
        assert ["kill", "-9", "4242"] in kill_calls
        # SIGTERM must be attempted before SIGKILL.
        assert kill_calls.index(["kill", "-15", "4242"]) < kill_calls.index(["kill", "-9", "4242"])

    def test_stop_no_sigkill_when_port_closes_after_sigterm(self):
        """If the process exits promptly after SIGTERM, stop() must not
        also send SIGKILL — the whole point of the grace period."""
        sm = self._make()
        calls = []

        def _fake_run(cmd, **kwargs):
            calls.append(cmd)
            result = mock.MagicMock()
            if cmd[0] == "lsof":
                result.stdout = "4242\n"
            return result

        with mock.patch("subprocess.run", side_effect=_fake_run), \
             mock.patch.object(sm, "_is_port_open", return_value=False), \
             mock.patch("time.sleep"):
            sm.stop("spec:qwen3-14b")

        kill_calls = [c for c in calls if c[0] == "kill"]
        assert ["kill", "-15", "4242"] in kill_calls
        assert ["kill", "-9", "4242"] not in kill_calls

    def test_stop_known_returns_ok(self):
        sm = self._make()
        with mock.patch("subprocess.run") as mock_run:
            mock_result = mock.MagicMock()
            mock_result.stdout = ""
            mock_run.return_value = mock_result
            result = sm.stop("spec:qwen3-14b")
        assert result["ok"] is True

    def test_stop_all_returns_dict(self):
        from ollama_arena.backends.spec import SPEC_SERVERS
        sm = self._make()
        with mock.patch("subprocess.run") as mock_run:
            mock_result = mock.MagicMock()
            mock_result.stdout = ""
            mock_run.return_value = mock_result
            result = sm.stop_all()
        assert isinstance(result, dict)
        assert len(result) == len(SPEC_SERVERS)

    def test_is_port_open_false_on_refused(self):
        from ollama_arena.backends.spec import SpecManager
        import socket
        with mock.patch("socket.create_connection", side_effect=OSError("refused")):
            result = SpecManager._is_port_open(8888)
        assert result is False

    def test_is_port_open_true_on_success(self):
        from ollama_arena.backends.spec import SpecManager
        mock_conn = mock.MagicMock()
        mock_conn.__enter__ = mock.MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = mock.MagicMock(return_value=False)
        with mock.patch("socket.create_connection", return_value=mock_conn):
            result = SpecManager._is_port_open(8888)
        assert result is True

    def test_stop_tracked_proc_terminates_gracefully(self):
        """stop() tries SIGTERM (terminate) first and only escalates to
        kill() if the process doesn't exit within the grace period."""
        sm = self._make()
        mock_proc = mock.MagicMock()
        mock_proc.wait.return_value = 0  # exits promptly after terminate()
        sm._procs["spec:qwen3-14b"] = mock_proc
        with mock.patch("subprocess.run") as mock_run:
            mock_result = mock.MagicMock()
            mock_result.stdout = ""
            mock_run.return_value = mock_result
            sm.stop("spec:qwen3-14b")
        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_not_called()
        assert "spec:qwen3-14b" not in sm._procs

    def test_stop_tracked_proc_escalates_to_kill_on_timeout(self):
        """If the process ignores SIGTERM and wait() times out, stop()
        falls back to kill() (SIGKILL) rather than leaving it running."""
        sm = self._make()
        mock_proc = mock.MagicMock()
        mock_proc.wait.side_effect = subprocess.TimeoutExpired(cmd="x", timeout=3)
        sm._procs["spec:qwen3-14b"] = mock_proc
        with mock.patch("subprocess.run") as mock_run:
            mock_result = mock.MagicMock()
            mock_result.stdout = ""
            mock_run.return_value = mock_result
            sm.stop("spec:qwen3-14b")
        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()
        assert "spec:qwen3-14b" not in sm._procs
