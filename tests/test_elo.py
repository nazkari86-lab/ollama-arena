"""Tests for elo.py — EloStore.record_match() transaction atomicity.

record_match() used to make 4 separate DB calls (upsert_rating x2,
apply_match_stats, insert_match_log, [+upsert_category_rating]), each
opening and committing its own SQLite connection/transaction. A crash
partway through (e.g. insert_match_log raising) left the ratings table
updated with no corresponding match_log row -- ratings desynced from
match history, with no way to tell from the leaderboard alone that the
write was incomplete.

This was flagged (not fixed) during the Storage/SQLite quality pass and
is fixed here by threading one shared `write_conn` through every write in
record_match(), so a mid-sequence exception rolls back all of them
together instead of leaving a partial write.
"""
from __future__ import annotations

import os
import tempfile

import pytest

from ollama_arena.elo import EloStore


@pytest.fixture
def store(tmp_path):
    db = str(tmp_path / "arena.db")
    return EloStore(db_path=db)


class TestRecordMatchAtomicity:
    def test_happy_path_commits_ratings_and_match_log_together(self, store):
        store.record_match("m1", "m2", "coding", 1.0, 0.0)
        lb = store.leaderboard()
        assert {row["model"] for row in lb} == {"m1", "m2"}
        assert store.last_match_id() == 1

    def test_crash_in_insert_match_log_rolls_back_rating_updates(self, store, monkeypatch):
        """The core regression: a crash after the rating upserts but
        before/during the match_log insert must not leave ratings updated
        with no matching match_log row.
        """
        def boom(*args, **kwargs):
            raise RuntimeError("simulated crash mid-sequence")

        monkeypatch.setattr(store._matches, "insert_match_log", boom)

        store.record_match("m1", "m2", "coding", 1.0, 0.0)

        # Before the fix: leaderboard showed m1/m2 with moved ratings even
        # though last_match_id() was still 0 (match_log insert never
        # landed) -- a desync between ratings and match history.
        assert store.leaderboard() == []
        assert store.last_match_id() == 0

    def test_crash_in_apply_match_stats_rolls_back_rating_upserts(self, store, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError("simulated crash mid-sequence")

        monkeypatch.setattr(store._ratings, "apply_match_stats", boom)

        store.record_match("m1", "m2", "coding", 1.0, 0.0)

        assert store.leaderboard() == []
        assert store.last_match_id() == 0

    def test_crash_in_category_rating_rolls_back_everything(self, store, monkeypatch):
        """Per-category ELO write is the 5th/last step in the sequence; a
        crash there must roll back the global rating + match_log writes
        that already happened earlier in the same call, too.
        """
        def boom(*args, **kwargs):
            raise RuntimeError("simulated crash mid-sequence")

        monkeypatch.setattr(store._ratings, "upsert_category_rating", boom)

        store.record_match("m1", "m2", "coding", 1.0, 0.0)

        assert store.leaderboard() == []
        assert store.last_match_id() == 0
        assert store.model_category_elos("m1") == []

    def test_no_category_skips_category_write_without_error(self, store):
        """category='' must not attempt a category-rating write at all."""
        store.record_match("m1", "m2", "", 1.0, 0.0)
        assert store.last_match_id() == 1
        assert store.model_category_elos("m1") == []

    def test_second_match_accumulates_correctly(self, store):
        """Two successful record_match calls must each commit fully and
        independently -- guards against the shared-connection refactor
        accidentally reusing/leaking a connection across calls."""
        store.record_match("m1", "m2", "coding", 1.0, 0.0)
        store.record_match("m1", "m2", "coding", 1.0, 0.0)
        lb = store.leaderboard()
        m1 = next(r for r in lb if r["model"] == "m1")
        assert m1["wins"] == 2
        assert m1["matches"] == 2
        assert store.last_match_id() == 2


class TestRecordMatchDuration:
    """record_match() used to hardcode duration_s=0.0 into the webhook
    notification regardless of how long the match actually took (flagged
    during the Webhooks quality pass). It now accepts a real duration_s
    and forwards it to notify_match instead of a hardcoded zero."""

    def test_duration_s_forwarded_to_webhook_notification(self, store, monkeypatch):
        captured = {}

        def fake_notify_match(*args, **kwargs):
            captured.update(kwargs)

        monkeypatch.setattr("ollama_arena.webhooks.notify_match", fake_notify_match)
        store.record_match("m1", "m2", "coding", 1.0, 0.0, duration_s=12.5)
        assert captured.get("duration_s") == 12.5

    def test_duration_s_defaults_to_zero_for_callers_that_omit_it(self, store, monkeypatch):
        captured = {}

        def fake_notify_match(*args, **kwargs):
            captured.update(kwargs)

        monkeypatch.setattr("ollama_arena.webhooks.notify_match", fake_notify_match)
        store.record_match("m1", "m2", "coding", 1.0, 0.0)
        assert captured.get("duration_s") == 0.0
