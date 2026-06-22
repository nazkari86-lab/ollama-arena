"""Startup banner — the printed 'url:' line must reflect real reachability."""
import pytest

fastapi = pytest.importorskip("fastapi")

import ollama_arena.web as web_module
from ollama_arena.web import run_web


def _run_and_capture(capsys, monkeypatch, **run_web_kwargs):
    import uvicorn

    def fake_run(app, **_):
        pass

    monkeypatch.setattr(uvicorn, "run", fake_run)
    run_web(**run_web_kwargs)
    return capsys.readouterr().out


def test_binding_all_interfaces_shows_lan_ip_not_localhost(capsys, monkeypatch):
    monkeypatch.setattr(web_module, "_detect_lan_ip", lambda: "192.168.1.42")
    out = _run_and_capture(
        capsys, monkeypatch, host="0.0.0.0", port=7860, db_path=":memory:"
    )
    assert "http://192.168.1.42:7860" in out
    assert "localhost" not in out


def test_binding_loopback_only_still_shows_loopback_not_lan_ip(capsys, monkeypatch):
    # If the user explicitly restricted to 127.0.0.1, the server genuinely
    # isn't reachable via the LAN IP -- the banner must not claim otherwise.
    monkeypatch.setattr(web_module, "_detect_lan_ip", lambda: "192.168.1.42")
    out = _run_and_capture(
        capsys, monkeypatch, host="127.0.0.1", port=7860, db_path=":memory:"
    )
    assert "http://127.0.0.1:7860" in out
    assert "192.168.1.42" not in out


def test_lan_ip_detection_failure_falls_back_to_localhost(capsys, monkeypatch):
    def _raise():
        raise OSError("network unreachable")

    monkeypatch.setattr(web_module, "_detect_lan_ip", _raise)
    out = _run_and_capture(
        capsys, monkeypatch, host="0.0.0.0", port=7860, db_path=":memory:"
    )
    assert "http://localhost:7860" in out
