"""Tests for SQLite connection pooling and optimization."""
import os
import sqlite3
import tempfile
import pytest
from ollama_arena.storage.sqlite._conn import (
    read_conn,
    write_conn,
    get_connection,
    close_all_connections,
    get_pool_stats,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    # Cleanup
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


class TestBasicConnections:
    """Test basic connection functionality."""

    def test_read_connection(self, temp_db):
        """Test creating a read connection."""
        conn = read_conn(temp_db)
        assert conn is not None
        conn.close()

    def test_write_connection(self, temp_db):
        """Test creating a write connection."""
        conn = write_conn(temp_db)
        assert conn is not None
        conn.close()

    def test_connection_isolation(self, temp_db):
        """Test that write connections have proper isolation."""
        conn = write_conn(temp_db)
        # Create a table
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.commit()

        # Check if table exists
        result = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone()
        assert result is not None
        conn.close()


class TestConnectionPooling:
    """Test connection pooling functionality."""

    def test_read_connection_pooling(self, temp_db):
        """Test that read connections are pooled."""
        close_all_connections()

        # Create first connection
        conn1 = read_conn(temp_db)
        pool_stats_1 = get_pool_stats()
        assert pool_stats_1["total_connections"] >= 1

        # Create second connection - should reuse pooled connection
        conn2 = read_conn(temp_db)
        pool_stats_2 = get_pool_stats()
        assert pool_stats_2["total_connections"] == pool_stats_1["total_connections"]

        conn1.close()
        conn2.close()

    def test_write_connection_not_pooled(self, temp_db):
        """Test that write connections are not pooled."""
        close_all_connections()

        # Create write connection
        conn1 = write_conn(temp_db)
        pool_stats_1 = get_pool_stats()
        # Write connections should not be in pool
        assert pool_stats_1["total_connections"] == 0

        conn1.close()

    def test_pool_capacity_limit(self, temp_db):
        """Test that pool respects capacity limits."""
        close_all_connections()

        # Create connections up to capacity
        connections = []
        for i in range(10):  # More than default pool size
            conn = read_conn(temp_db)
            connections.append(conn)

        pool_stats = get_pool_stats()
        # Pool should not exceed max size
        assert pool_stats["total_connections"] <= pool_stats["max_pool_size"]

        for conn in connections:
            conn.close()

    def test_close_all_connections(self, temp_db):
        """Test closing all pooled connections."""
        close_all_connections()

        # Create some connections
        conn1 = read_conn(temp_db)
        conn2 = read_conn(temp_db)

        # Close all
        close_all_connections()

        pool_stats = get_pool_stats()
        assert pool_stats["total_connections"] == 0

        conn1.close()
        conn2.close()


class TestContextManager:
    """Test context manager for connections."""

    def test_context_manager_auto_commit(self, temp_db):
        """Test that context manager auto-commits on success."""
        with get_connection(temp_db, readonly=False) as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.execute("INSERT INTO test VALUES (1)")

        # Verify data was committed
        with get_connection(temp_db, readonly=True) as conn:
            result = conn.execute("SELECT COUNT(*) FROM test").fetchone()
            assert result[0] == 1

    def test_context_manager_auto_rollback(self, temp_db):
        """Test that context manager auto-rollbacks on error."""
        # First create the table outside of the transaction to test data rollback
        with get_connection(temp_db, readonly=False) as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")

        try:
            with get_connection(temp_db, readonly=False) as conn:
                # Insert data that should be rolled back
                conn.execute("INSERT INTO test VALUES (1)")
                conn.execute("INSERT INTO test VALUES (2)")
                raise ValueError("Simulated error")
        except ValueError:
            pass

        # Verify data was rolled back
        with get_connection(temp_db, readonly=True) as conn:
            result = conn.execute("SELECT COUNT(*) FROM test").fetchone()
            assert result[0] == 0, f"Expected 0 rows after rollback, but got {result[0]}"

    def test_context_manager_readonly(self, temp_db):
        """Test read-only context manager."""
        # Setup data
        with get_connection(temp_db, readonly=False) as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.execute("INSERT INTO test VALUES (1)")

        # Read with context manager
        with get_connection(temp_db, readonly=True) as conn:
            result = conn.execute("SELECT * FROM test").fetchall()
            assert len(result) == 1


class TestPerformanceOptimizations:
    """Test that performance optimizations are applied."""

    def test_wal_mode_enabled(self, temp_db):
        """Test that WAL mode is enabled."""
        conn = read_conn(temp_db)
        result = conn.execute("PRAGMA journal_mode").fetchone()
        assert result[0] == "wal"
        conn.close()

    def test_cache_size_configured(self, temp_db):
        """Test that cache size is configured."""
        conn = read_conn(temp_db)
        result = conn.execute("PRAGMA cache_size").fetchone()
        # Cache size should be negative (absolute value in KB)
        assert result[0] < 0
        conn.close()

    def test_synchronous_normal(self, temp_db):
        """Test that synchronous mode is NORMAL."""
        conn = read_conn(temp_db)
        result = conn.execute("PRAGMA synchronous").fetchone()
        assert result[0] in (1, 2)  # NORMAL or FULL
        conn.close()


class TestThreadSafety:
    """Regression tests for the per-thread pool keying fix.

    Previously the pool was keyed only by db_path, so concurrent threads
    shared a single sqlite3.Connection object for reads on the same
    database. That corrupts cursor state across threads (one thread's
    fetchone() can observe another thread's interleaved result, or None)
    even with check_same_thread=False, because sqlite3 connections aren't
    safe for concurrent use from multiple threads without serialization.
    """

    def test_concurrent_reads_do_not_corrupt_results(self, temp_db):
        import threading

        close_all_connections()
        cx = sqlite3.connect(temp_db)
        cx.execute("CREATE TABLE t (id INTEGER)")
        for i in range(50):
            cx.execute("INSERT INTO t VALUES (?)", (i,))
        cx.commit()
        cx.close()

        errors = []

        def worker():
            try:
                for _ in range(100):
                    c = read_conn(temp_db)
                    row = c.execute("SELECT COUNT(*) FROM t").fetchone()
                    if row is None or row[0] != 50:
                        raise AssertionError(f"corrupted read: {row}")
            except Exception as e:  # noqa: BLE001 - capturing for assertion below
                errors.append(repr(e))

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"concurrent reads corrupted: {errors[:3]} (total {len(errors)})"
        close_all_connections()

    def test_different_threads_get_different_pooled_connections(self, temp_db):
        import threading

        close_all_connections()
        conns = {}
        barrier = threading.Barrier(2)

        def worker(name):
            conns[name] = read_conn(temp_db)
            # Hold both threads alive simultaneously so neither's OS thread
            # id can be recycled before the comparison below runs.
            barrier.wait()

        t1 = threading.Thread(target=worker, args=("t1",))
        t2 = threading.Thread(target=worker, args=("t2",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Each thread's connection wraps a distinct underlying sqlite3.Connection.
        assert conns["t1"]._conn is not conns["t2"]._conn
        close_all_connections()


class TestReadConnOverflowCloses:
    """Regression tests for the read-connection-overflow leak fix.

    Before the fix, `with read_conn(db) as cx:` never closed cx when the
    pool was at capacity (overflow connections), because bare
    sqlite3.Connection.__exit__ only commits/rolls back. Under sustained
    concurrency (more callers than _pool_max_size) that leaked one
    unclosed connection (and its WAL-related fds) per overflow call until
    the garbage collector happened to run.
    """

    def test_pooled_connection_stays_open_after_with_block(self, temp_db):
        close_all_connections()
        with read_conn(temp_db) as cx:
            cx.execute("SELECT 1")
        # Still pooled — same underlying connection still usable, not closed.
        stats = get_pool_stats()
        assert stats["total_connections"] >= 1
        with read_conn(temp_db) as cx2:
            cx2.execute("SELECT 1")  # would raise ProgrammingError if closed
        close_all_connections()

    def test_overflow_connection_is_closed_after_with_block(self, temp_db):
        from ollama_arena.storage.sqlite._conn import _pool_max_size

        close_all_connections()
        # Fill the pool to capacity with held-open `with` blocks so the next
        # read_conn() call is forced to create an overflow (unpooled) connection.
        import contextlib

        with contextlib.ExitStack() as stack:
            held = []
            for _ in range(_pool_max_size):
                cx = stack.enter_context(read_conn(temp_db + str(_)))
                held.append(cx)

            # This db_path is new -> still goes through the same thread's pool
            # key space; pool is at capacity so this call must overflow.
            overflow_wrapper = read_conn(temp_db + "_overflow")
            with overflow_wrapper as cx:
                cx.execute("SELECT 1")
            # After the with-block exits, the overflow connection must be
            # closed — further use should raise.
            with pytest.raises(sqlite3.ProgrammingError):
                overflow_wrapper._conn.execute("SELECT 1")
        close_all_connections()


class TestPoolStats:
    """Test pool statistics functionality."""

    def test_pool_stats_structure(self, temp_db):
        """Test that pool stats have expected structure."""
        stats = get_pool_stats()
        assert "total_connections" in stats
        assert "max_pool_size" in stats
        assert "utilization" in stats

    def test_pool_stats_update(self, temp_db):
        """Test that pool stats update with connections."""
        close_all_connections()

        stats_before = get_pool_stats()
        assert stats_before["total_connections"] == 0

        conn = read_conn(temp_db)
        stats_after = get_pool_stats()
        assert stats_after["total_connections"] > 0

        conn.close()

    def test_utilization_calculation(self, temp_db):
        """Test that utilization is calculated correctly."""
        close_all_connections()

        # Add read connections to pool (write connections are not pooled)
        for _ in range(3):
            conn = read_conn(temp_db)
            conn.close()

        stats = get_pool_stats()
        # Pool should have our connections
        assert stats["total_connections"] >= 1  # At least one connection in pool
        assert stats["utilization"] >= 0.0  # Valid utilization value
        assert stats["utilization"] <= 1.0  # Cannot exceed 100%