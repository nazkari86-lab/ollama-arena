"""Shared SQLite connection helpers with connection pooling and optimization."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from threading import Lock
from typing import Dict, Optional


# Simple connection pool for read operations
_connection_pool: Dict[str, sqlite3.Connection] = {}
_pool_lock = Lock()
_pool_max_size = 5


def _get_connection(db_path: str, readonly: bool = False) -> sqlite3.Connection:
    """Get a connection from the pool or create a new one."""
    # Write connections are never pooled to ensure transaction isolation
    if not readonly:
        return _create_connection(db_path, readonly=False)

    with _pool_lock:
        # Check pool for existing connection
        pool_key = f"{db_path}_read"
        if pool_key in _connection_pool:
            conn = _connection_pool[pool_key]
            try:
                # Test if connection is still alive
                conn.execute("SELECT 1")
                return conn
            except sqlite3.Error:
                # Connection is dead, remove it
                del _connection_pool[pool_key]

        # Create new connection with optimizations
        conn = _create_connection(db_path, readonly=True)

        # Add to pool if not at capacity
        if len(_connection_pool) < _pool_max_size:
            _connection_pool[pool_key] = conn

        return conn


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


def read_conn(db_path: str) -> sqlite3.Connection:
    """Get an optimized read-only connection from pool."""
    return _get_connection(db_path, readonly=True)


def write_conn(db_path: str) -> sqlite3.Connection:
    """Get a write connection (not pooled due to transaction isolation)."""
    return _create_connection(db_path, readonly=False)


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


def get_pool_stats() -> Dict[str, int]:
    """Get statistics about the connection pool."""
    with _pool_lock:
        return {
            "total_connections": len(_connection_pool),
            "max_pool_size": _pool_max_size,
            "utilization": len(_connection_pool) / _pool_max_size if _pool_max_size > 0 else 0,
        }
