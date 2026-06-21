"""Tests for telemetry storage — SQLiteTelemetryStorage (SQLite-backed)."""
from __future__ import annotations

import time

import pytest


def _make_record(**kw):
    from ollama_arena.telemetry.base import TelemetryRecord
    defaults = dict(timestamp=time.time(), model="llama3:8b", backend="ollama")
    defaults.update(kw)
    return TelemetryRecord(**defaults)


class TestSQLiteTelemetryStorage:
    def _make(self, tmp_path):
        from ollama_arena.telemetry.base import SQLiteTelemetryStorage
        return SQLiteTelemetryStorage(db_path=str(tmp_path / "telemetry.db"))

    def test_init_does_not_crash(self, tmp_path):
        s = self._make(tmp_path)
        assert s is not None

    def test_db_path_stored(self, tmp_path):
        db_path = str(tmp_path / "telemetry.db")
        from ollama_arena.telemetry.base import SQLiteTelemetryStorage
        s = SQLiteTelemetryStorage(db_path=db_path)
        assert s.db_path == db_path

    def test_store_record_no_crash(self, tmp_path):
        s = self._make(tmp_path)
        r = _make_record(tps=42.0, tokens_out=100)
        s.store(r)  # Must not raise

    def test_query_empty_returns_empty_list(self, tmp_path):
        s = self._make(tmp_path)
        result = s.query()
        assert result == []

    def test_query_after_store_returns_record(self, tmp_path):
        from ollama_arena.telemetry.base import TelemetryRecord
        s = self._make(tmp_path)
        s.store(_make_record(model="phi3:3b", tps=30.0, tokens_out=50))
        result = s.query()
        assert len(result) == 1
        assert isinstance(result[0], TelemetryRecord)

    def test_query_filter_by_model(self, tmp_path):
        s = self._make(tmp_path)
        s.store(_make_record(model="llama3:8b"))
        s.store(_make_record(model="phi3:3b"))
        result = s.query(model="llama3:8b")
        assert len(result) == 1
        assert result[0].model == "llama3:8b"

    def test_query_preserves_fields(self, tmp_path):
        s = self._make(tmp_path)
        s.store(_make_record(model="llama3:8b", tps=55.5, tokens_out=200))
        result = s.query(model="llama3:8b")
        assert result[0].tps == pytest.approx(55.5)
        assert result[0].tokens_out == 200

    def test_query_limit_respected(self, tmp_path):
        s = self._make(tmp_path)
        for _ in range(5):
            s.store(_make_record())
        result = s.query(limit=3)
        assert len(result) == 3

    def test_store_with_hardware_info(self, tmp_path):
        s = self._make(tmp_path)
        r = _make_record(hardware_info={"platform": "nvidia", "device_name": "RTX 4090"})
        s.store(r)
        result = s.query()
        assert result[0].hardware_info.get("platform") == "nvidia"

    def test_aggregate_empty_returns_dict(self, tmp_path):
        s = self._make(tmp_path)
        result = s.aggregate()
        assert isinstance(result, dict)

    def test_aggregate_by_model(self, tmp_path):
        s = self._make(tmp_path)
        s.store(_make_record(model="llama3:8b", tps=40.0))
        s.store(_make_record(model="llama3:8b", tps=60.0))
        result = s.aggregate(group_by="model")
        assert "model" in result

    def test_aggregate_by_platform(self, tmp_path):
        s = self._make(tmp_path)
        s.store(_make_record())
        result = s.aggregate(group_by="platform")
        assert isinstance(result, dict)

    def test_aggregate_by_quantization(self, tmp_path):
        s = self._make(tmp_path)
        s.store(_make_record(quantization="q4_k_m"))
        result = s.aggregate(group_by="quantization")
        assert isinstance(result, dict)

    def test_query_with_time_range(self, tmp_path):
        s = self._make(tmp_path)
        t = time.time()
        s.store(_make_record(timestamp=t - 100))
        s.store(_make_record(timestamp=t - 50))
        s.store(_make_record(timestamp=t))
        result = s.query(start_time=t - 75)
        assert len(result) == 2

    def test_query_end_time_filter(self, tmp_path):
        s = self._make(tmp_path)
        t = time.time()
        s.store(_make_record(timestamp=t - 100))
        s.store(_make_record(timestamp=t))
        result = s.query(end_time=t - 50)
        assert len(result) == 1

    def test_conn_closes_connection_after_use(self, tmp_path):
        # Regression: _conn() used to return a raw sqlite3.Connection used
        # only as `with self._conn() as cx:`. sqlite3.Connection's
        # __exit__ commits/rolls back but does NOT close the connection,
        # so every store()/query()/aggregate() call leaked an open
        # connection (and a file descriptor) for the life of the process.
        # _conn() is now itself a context manager that closes the
        # connection on exit.
        s = self._make(tmp_path)
        with s._conn() as cx:
            cx.execute("SELECT 1")
        import sqlite3
        with pytest.raises(sqlite3.ProgrammingError):
            cx.execute("SELECT 1")  # connection must be closed by now

    def test_repeated_store_does_not_leak_open_file_handles(self, tmp_path):
        # End-to-end regression check using the public API and the OS's
        # own view of open file descriptors: many store() calls in a row
        # must not accumulate open handles on the db file. Before the
        # fix, each call leaked one connection (and its underlying fd)
        # because sqlite3.Connection.__exit__ commits/rolls back but does
        # not close. Skipped on platforms without `lsof`.
        import os
        import shutil
        import subprocess

        if shutil.which("lsof") is None:
            pytest.skip("lsof not available on this platform")

        s = self._make(tmp_path)
        db_name = os.path.basename(s.db_path)
        pid = os.getpid()

        for _ in range(10):
            s.store(_make_record())

        out = subprocess.run(
            ["lsof", "-p", str(pid)], capture_output=True, text=True
        ).stdout
        open_handles = out.count(db_name)
        assert open_handles <= 1, (
            f"expected at most 1 open handle on {db_name}, found {open_handles} "
            "after 10 store() calls -- connections are leaking"
        )
