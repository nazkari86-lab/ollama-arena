"""Shared pytest configuration — env must be set before ollama_arena.web import."""
import os
import platform
import subprocess

import pytest

os.environ.setdefault("ARENA_ALLOWED_ORIGINS", "http://localhost:7860")
os.environ.setdefault("ARENA_RL_PLAYGROUND", "3/minute")
os.environ.setdefault("ARENA_RL_DEFAULT", "5/minute")


@pytest.fixture(autouse=True)
def _block_background_process_spawn(monkeypatch):
    """Refuse subprocess.Popen(..., start_new_session=True) by default so an
    unmocked route (e.g. POST /api/spec/start_all -> SpecManager.start) can't
    detach a real, GPU-loaded llama-server into the background instead of
    being exercised against a mock. start_new_session=True is the signature
    of a fire-and-forget background daemon (what SpecManager.start does);
    short-lived foreground probes (e.g. hardware checks shelling out to
    `rocm-smi`/`uname` via subprocess.run) don't set it and are left to run
    for real, since they fail/succeed near-instantly with no resource risk.
    A test that genuinely needs to spawn a background process should
    monkeypatch/mock Popen itself, which takes precedence over this fixture.
    """
    real_popen = subprocess.Popen

    def _guarded(*args, **kwargs):
        if kwargs.get("start_new_session"):
            raise RuntimeError(
                "subprocess.Popen(start_new_session=True) is blocked by default in tests — "
                "mock it explicitly (mock.patch('subprocess.Popen', ...)) if this test needs it."
            )
        return real_popen(*args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", _guarded)


@pytest.fixture(autouse=True)
def _stable_platform_processor(monkeypatch):
    """platform.processor() shells out to `uname -p` on macOS, which would
    otherwise hit the subprocess.Popen guard above. Pin it so hardware
    attestation code (ollama_arena.p2p.crypto_proof) is also deterministic
    across machines instead of depending on the real subprocess guard.
    """
    monkeypatch.setattr(platform, "processor", lambda: "test-cpu")


@pytest.fixture(autouse=True)
def _close_sqlite_pool():
    """Close pooled read-only SQLite connections after every test to avoid ResourceWarning."""
    yield
    try:
        from ollama_arena.storage.sqlite._conn import close_all_connections
        close_all_connections()
    except Exception:
        pass
