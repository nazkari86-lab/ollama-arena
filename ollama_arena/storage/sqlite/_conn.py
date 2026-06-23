"""Shared SQLite connection helpers with connection pooling and optimization."""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from threading import Lock
from typing import Dict, Tuple


# Simple connection pool for read operations.
#
# Keyed by (db_path, thread_ident) rather than just db_path: a single
# sqlite3.Connection handed out to two threads concurrently corrupts cursor
# state across unrelated queries (one thread's fetchone() can see another
# thread's interleaved result, or None) even though check_same_thread=False
# suppresses sqlite3's own thread-safety guard. Scoping the pool per-thread
# keeps the reuse benefit within a thread while eliminating that race.
_connection_pool: Dict[Tuple[str, int], sqlite3.Connection] = {}
_pool_lock = Lock()
_pool_max_size = 5


class _ReadConn:
    """Wraps a read sqlite3.Connection so 'with read_conn() as cx:' is safe.

    Pooled connections must stay open after the `with` block (they're reused
    by the next caller on this thread) — so __exit__ is a no-op for those.
    Overflow connections (pool was at capacity) are never reused and were
    previously never closed by `with read_conn(...) as cx:` callers, since
    sqlite3.Connection.__exit__ only commits/rolls back. Under sustained
    concurrency (more threads than _pool_max_size) that leaked one fd per
    overflow call until GC happened to run. __exit__ now closes those.
    """

    __slots__ = ("_conn", "_pooled")

    def __init__(self, conn: sqlite3.Connection, pooled: bool) -> None:
        self._conn = conn
        self._pooled = pooled

    def __enter__(self) -> sqlite3.Connection:
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._pooled:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass
        return False

    def __getattr__(self, name: str):
        return getattr(self._conn, name)


class _WriteConn:
    """Wraps a write sqlite3.Connection so 'with write_conn() as cx:' auto-closes.

    sqlite3.Connection's own __exit__ only commits/rolls back — it never closes.
    This wrapper adds the close() call in __exit__ so callers don't leak handles.
    """

    __slots__ = ("_conn",)

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ── context manager ───────────────────────────────────────────────────────

    def __enter__(self) -> sqlite3.Connection:
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is None:
                self._conn.commit()
            else:
                try:
                    self._conn.rollback()
                except sqlite3.Error:
                    pass
        finally:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass
        return False

    # ── delegate attribute access so bare conn = write_conn() still works ─────

    def __getattr__(self, name: str):
        return getattr(self._conn, name)


def _get_connection(db_path: str, readonly: bool = False) -> sqlite3.Connection:
    """Get a connection from the pool or create a new one."""
    conn, _pooled = _get_connection_ex(db_path, readonly=readonly)
    return conn


def _get_connection_ex(db_path: str, readonly: bool = False) -> "tuple[sqlite3.Connection, bool]":
    """Like _get_connection but also reports whether the connection is
    sitting in the pool (and therefore must NOT be closed by the caller)."""
    # Write connections are never pooled to ensure transaction isolation
    if not readonly:
        return _create_connection(db_path, readonly=False), False

    with _pool_lock:
        # Check pool for existing connection (scoped to this thread — see
        # module docstring on _connection_pool for why).
        pool_key = (db_path, threading.get_ident())
        if pool_key in _connection_pool:
            conn = _connection_pool[pool_key]
            try:
                # Test if connection is still alive
                conn.execute("SELECT 1")
                return conn, True
            except sqlite3.Error:
                # Connection is dead, remove it
                del _connection_pool[pool_key]

        # Create new connection with optimizations
        conn = _create_connection(db_path, readonly=True)

        # Add to pool if not at capacity
        if len(_connection_pool) < _pool_max_size:
            _connection_pool[pool_key] = conn
            return conn, True

        return conn, False


def _create_connection(db_path: str, readonly: bool = False) -> sqlite3.Connection:
    """Create a new optimized connection."""
    if readonly:
        # Read-only connections: autocommit mode (isolation_level=None)
        conn = sqlite3.connect(
            db_path,
            timeout=30.0,
            isolation_level=None,
            check_same_thread=False,
        )
    else:
        # Write connections: standard transaction mode
        conn = sqlite3.connect(
            db_path,
            timeout=30.0,
            isolation_level="IMMEDIATE",
            check_same_thread=False,
        )

    # Performance optimizations
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        # Fallback for temporary filesystems where WAL is not supported
        conn.execute("PRAGMA journal_mode=MEMORY")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA mmap_size=268435456")  # 256MB memory-mapped I/O

    if readonly:
        # Additional optimizations for read-only connections
        conn.execute("PRAGMA query_only=1")
        conn.execute("PRAGMA locking_mode=SHARED")

    return conn


def read_conn(db_path: str) -> "_ReadConn":
    """Get an optimized read-only connection from pool.

    Returns a _ReadConn wrapper: pooled connections stay open (and in the
    pool) after 'with read_conn(db) as cx:' exits, but overflow connections
    (pool at capacity) are closed automatically so they don't leak file
    descriptors under sustained concurrency. Bare attribute access (e.g.
    `read_conn(db).execute(...)` without `with`) is delegated to the
    underlying sqlite3.Connection unchanged.
    """
    conn, pooled = _get_connection_ex(db_path, readonly=True)
    return _ReadConn(conn, pooled)


def write_conn(db_path: str) -> "_WriteConn":
    """Get a write connection (not pooled due to transaction isolation).

    Returns a _WriteConn wrapper so 'with write_conn() as cx:' commits and
    closes the connection automatically. Bare attribute access is delegated to
    the underlying sqlite3.Connection for callers that don't use 'with'.
    """
    return _WriteConn(_create_connection(db_path, readonly=False))


@contextmanager
def get_connection(db_path: str, readonly: bool = False):
    """Context manager for automatic connection cleanup."""
    conn = _get_connection(db_path, readonly=readonly)
    try:
        yield conn
        if not readonly:
            conn.commit()
    except Exception:
        if not readonly:
            try:
                conn.rollback()
            except sqlite3.Error:
                pass  # Connection might be in a bad state
        raise
    finally:
        # Only close write connections; keep read connections in pool
        if not readonly:
            try:
                conn.close()
            except sqlite3.Error:
                pass  # Ignore close errors


def close_all_connections():
    """Close all pooled connections. Call this when shutting down the application."""
    with _pool_lock:
        for conn in _connection_pool.values():
            try:
                conn.close()
            except sqlite3.Error:
                pass
        _connection_pool.clear()


def get_pool_stats() -> Dict[str, float]:
    """Get statistics about the connection pool."""
    with _pool_lock:
        return {
            "total_connections": len(_connection_pool),
            "max_pool_size": _pool_max_size,
            "utilization": len(_connection_pool) / _pool_max_size if _pool_max_size > 0 else 0,
        }
