"""Tests for storage/sqlite/migrations.py — the forward-only migration runner.

This is the highest-risk file in the storage module: a migration bug can
corrupt someone's real arena.db schema with no rollback path once it has
run. These tests lock in the three properties that make the runner safe to
re-run on an already-migrated database:

1. Idempotency — running twice on the same DB is a no-op the second time.
2. Partial-failure safety — if a migration's SQL fails partway through,
   the transaction rolls back and user_version does NOT advance past the
   last successfully applied migration, so a later run can retry cleanly.
3. Column-add correctness — the _COLUMN_ADDS sniff-and-ALTER path actually
   adds every column it's supposed to, even for migrations whose `sql`
   body is pure SQL comments (a deliberately empty executescript).
"""
from __future__ import annotations

import sqlite3
from unittest.mock import patch

import pytest

from ollama_arena.storage.sqlite import migrations as mig


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_migrations.db")


class TestIdempotency:
    def test_fresh_db_applies_all_migrations(self, db_path):
        before, after = mig.apply_migrations(db_path)
        assert before == 0
        assert after == len(mig.MIGRATIONS)

    def test_rerun_on_already_migrated_db_is_noop(self, db_path):
        mig.apply_migrations(db_path)
        before, after = mig.apply_migrations(db_path)
        assert before == after == len(mig.MIGRATIONS)

    def test_rerun_does_not_duplicate_indexes_or_raise(self, db_path):
        mig.apply_migrations(db_path)
        mig.apply_migrations(db_path)
        mig.apply_migrations(db_path)  # three times for good measure
        cx = sqlite3.connect(db_path)
        try:
            tables = {r[0] for r in cx.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            assert {"ratings", "match_log", "task_detail", "royale_entries",
                    "category_ratings"} <= tables
        finally:
            cx.close()


class TestPartialFailureSafety:
    def test_failed_migration_rolls_back_and_keeps_version_at_last_good(self, db_path):
        patched = list(mig.MIGRATIONS)
        # Corrupt migration index 3 (#4, royale tables) with invalid SQL.
        patched[3] = (patched[3][0], "CREATE TABLE this is not valid sql ;;;")
        with patch.object(mig, "MIGRATIONS", patched):
            with pytest.raises(sqlite3.Error):
                mig.apply_migrations(db_path)

        cx = sqlite3.connect(db_path)
        try:
            version = mig.current_version(cx)
        finally:
            cx.close()
        # Migrations 1-3 succeeded; the broken #4 must not have advanced
        # user_version past 3.
        assert version == 3

    def test_recovery_run_after_failure_completes_to_target(self, db_path):
        patched = list(mig.MIGRATIONS)
        patched[3] = (patched[3][0], "CREATE TABLE this is not valid sql ;;;")
        with patch.object(mig, "MIGRATIONS", patched):
            with pytest.raises(sqlite3.Error):
                mig.apply_migrations(db_path)

        # Re-run with the real (unpatched) migration table — must pick up
        # from version 3 and reach the full target with no leftover damage.
        before, after = mig.apply_migrations(db_path)
        assert before == 3
        assert after == len(mig.MIGRATIONS)

        cx = sqlite3.connect(db_path)
        try:
            tables = {r[0] for r in cx.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            assert "royale_log" in tables and "royale_entries" in tables
            assert "category_ratings" in tables
        finally:
            cx.close()

    def test_failed_migration_does_not_partially_create_its_own_tables(self, db_path):
        """A migration whose script fails partway through must not leave
        behind tables from the failed statement — sqlite3 DDL is
        auto-committing per-statement, so this specifically checks that our
        failure injection (an early syntax error) prevented anything from
        that migration's body from landing."""
        patched = list(mig.MIGRATIONS)
        patched[3] = (patched[3][0], "CREATE TABLE this is not valid sql ;;;")
        with patch.object(mig, "MIGRATIONS", patched):
            with pytest.raises(sqlite3.Error):
                mig.apply_migrations(db_path)

        cx = sqlite3.connect(db_path)
        try:
            tables = {r[0] for r in cx.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            assert "royale_log" not in tables
            assert "royale_entries" not in tables
        finally:
            cx.close()


class TestColumnAdds:
    def test_comment_only_migrations_still_apply_their_column_adds(self, db_path):
        """Migrations #3, #5, #6 have `sql` bodies that are pure SQL
        comments (the actual DDL is done via _safe_add_column in Python).
        Confirms the comment-only executescript doesn't somehow skip the
        column-add step that follows it."""
        mig.apply_migrations(db_path)
        cx = sqlite3.connect(db_path)
        try:
            task_detail_cols = {r[1] for r in cx.execute("PRAGMA table_info(task_detail)")}
            match_log_cols = {r[1] for r in cx.execute("PRAGMA table_info(match_log)")}
            royale_cols = {r[1] for r in cx.execute("PRAGMA table_info(royale_entries)")}
        finally:
            cx.close()
        assert {"hallucination_a", "hallucination_b", "tool_call_a", "tool_call_b"} <= task_detail_cols
        assert "kind" in match_log_cols
        assert {"hallucination", "instruction"} <= royale_cols

    def test_safe_add_column_skips_existing_column(self, db_path):
        """_safe_add_column must be a no-op (not raise) if the column is
        already present — this is what makes column-add migrations safe
        to run twice."""
        mig.apply_migrations(db_path)
        cx = sqlite3.connect(db_path)
        try:
            # Re-running the same add against an already-migrated table
            # must not raise "duplicate column name".
            mig._safe_add_column(cx, "task_detail", "hallucination_a", "INTEGER")
            cols = {r[1] for r in cx.execute("PRAGMA table_info(task_detail)")}
            assert "hallucination_a" in cols
        finally:
            cx.close()


class TestCurrentVersion:
    def test_current_version_zero_on_fresh_connection(self, db_path):
        cx = sqlite3.connect(db_path)
        try:
            assert mig.current_version(cx) == 0
        finally:
            cx.close()
