"""Tests for storage/sqlite/ratings.py — SqliteRatingsRepository.

Focused on the bug-fix pass: apply_match_stats() previously silently
no-op'd (UPDATE affecting 0 rows) when called for a model with no existing
`ratings` row, with no signal that the stats bump was lost. That's exactly
the kind of silent-data-corruption failure mode worth a regression test —
ELO/win-loss corruption here is hard to notice until someone audits the
leaderboard much later.
"""
from __future__ import annotations

import logging
import time

import pytest


@pytest.fixture
def db_path(tmp_path):
    """Create a fully-migrated temp SQLite DB (never the real arena.db)."""
    from ollama_arena.storage.sqlite.migrations import apply_migrations
    path = str(tmp_path / "test_arena.db")
    apply_migrations(path)
    return path


@pytest.fixture
def repo(db_path):
    from ollama_arena.storage.sqlite.ratings import SqliteRatingsRepository
    return SqliteRatingsRepository(db_path=db_path)


# ──────────────────────────────────────────────────────────────────────────────
# get / upsert_rating
# ──────────────────────────────────────────────────────────────────────────────

class TestGetAndUpsert:
    def test_get_default_for_unknown_model(self, repo):
        assert repo.get("nonexistent-model") == 1200

    def test_upsert_then_get(self, repo):
        repo.upsert_rating("phi-4", 1234.5, time.time())
        assert repo.get("phi-4") == pytest.approx(1234.5)

    def test_upsert_conflict_updates_elo_not_stats(self, repo):
        """ON CONFLICT path: re-upserting must update elo without touching
        wins/losses/draws/matches (those are owned by apply_match_stats)."""
        now = time.time()
        repo.upsert_rating("phi-4", 1200, now)
        repo.apply_match_stats("phi-4", "qwen", 0.9, 0.1)
        repo.upsert_rating("qwen", 1190, now)
        repo.upsert_rating("phi-4", 1215, now + 1)  # re-upsert after a win
        lb = {row["model"]: row for row in repo.leaderboard()}
        assert lb["phi-4"]["elo"] == pytest.approx(1215)
        assert lb["phi-4"]["wins"] == 1  # preserved, not reset by the upsert


# ──────────────────────────────────────────────────────────────────────────────
# apply_match_stats — regression tests for the silent-no-op fix
# ──────────────────────────────────────────────────────────────────────────────

class TestApplyMatchStats:
    def test_normal_flow_updates_both_models(self, repo):
        now = time.time()
        repo.upsert_rating("a", 1200, now)
        repo.upsert_rating("b", 1200, now)
        repo.apply_match_stats("a", "b", 0.9, 0.1)
        lb = {row["model"]: row for row in repo.leaderboard()}
        assert lb["a"]["wins"] == 1 and lb["a"]["losses"] == 0
        assert lb["b"]["wins"] == 0 and lb["b"]["losses"] == 1
        assert lb["a"]["matches"] == 1 and lb["b"]["matches"] == 1

    def test_draw_increments_draws_for_both(self, repo):
        now = time.time()
        repo.upsert_rating("a", 1200, now)
        repo.upsert_rating("b", 1200, now)
        repo.apply_match_stats("a", "b", 0.5, 0.5)
        lb = {row["model"]: row for row in repo.leaderboard()}
        assert lb["a"]["draws"] == 1 and lb["b"]["draws"] == 1

    def test_missing_rating_row_does_not_raise_and_is_logged(self, repo, caplog):
        """Calling apply_match_stats for a model with no prior upsert_rating
        must not crash (matches pre-fix behavior — UPDATE just affects 0
        rows) but must now emit a warning so the lost stats bump is visible
        instead of disappearing silently."""
        with caplog.at_level(logging.WARNING, logger="arena.storage.ratings"):
            repo.apply_match_stats("ghost_a", "ghost_b", 0.9, 0.1)
        assert "ghost_a" in caplog.text
        assert "ghost_b" in caplog.text
        # No row was ever created — the model stays at the default.
        assert repo.get("ghost_a") == 1200
        assert repo.leaderboard() == []

    def test_partial_missing_row_only_warns_for_the_missing_one(self, repo, caplog):
        now = time.time()
        repo.upsert_rating("known", 1200, now)
        with caplog.at_level(logging.WARNING, logger="arena.storage.ratings"):
            repo.apply_match_stats("known", "ghost", 0.9, 0.1)
        assert "ghost" in caplog.text
        assert "no ratings row for 'known'" not in caplog.text
        lb = {row["model"]: row for row in repo.leaderboard()}
        assert lb["known"]["wins"] == 1


# ──────────────────────────────────────────────────────────────────────────────
# leaderboard / anti_leaderboard
# ──────────────────────────────────────────────────────────────────────────────

class TestLeaderboard:
    def test_empty_leaderboard(self, repo):
        assert repo.leaderboard() == []

    def test_leaderboard_ordered_by_elo_desc(self, repo):
        now = time.time()
        repo.upsert_rating("low", 1100, now)
        repo.upsert_rating("high", 1300, now)
        lb = repo.leaderboard()
        assert [row["model"] for row in lb] == ["high", "low"]
        assert [row["rank"] for row in lb] == [1, 2]

    def test_anti_leaderboard_empty(self, repo):
        assert repo.anti_leaderboard() == []


# ──────────────────────────────────────────────────────────────────────────────
# category ratings
# ──────────────────────────────────────────────────────────────────────────────

class TestCategoryRatings:
    def test_category_elo_default(self, repo):
        assert repo.get_category_elo("phi-4", "coding") == 1200

    def test_upsert_category_rating_accumulates_on_conflict(self, repo):
        now = time.time()
        repo.upsert_category_rating("a", "b", "coding", 1210, 1190, 0.9, 0.1, now)
        repo.upsert_category_rating("a", "b", "coding", 1220, 1180, 0.9, 0.1, now + 1)
        elos = {row["category"]: row for row in repo.all_category_elos("a")}
        assert elos["coding"]["elo"] == pytest.approx(1220)
        assert elos["coding"]["wins"] == 2
        assert elos["coding"]["matches"] == 2

    def test_category_leaderboard(self, repo):
        now = time.time()
        repo.upsert_category_rating("a", "b", "coding", 1220, 1180, 0.9, 0.1, now)
        lb = repo.category_leaderboard("coding")
        assert len(lb) == 2
        assert lb[0]["model"] == "a"


# ──────────────────────────────────────────────────────────────────────────────
# record_royale_elo
# ──────────────────────────────────────────────────────────────────────────────

class TestRecordRoyaleElo:
    def test_royale_elo_updates_all_models(self, repo):
        results = [
            {"model": "a", "score": 0.9},
            {"model": "b", "score": 0.5},
            {"model": "c", "score": 0.1},
        ]
        repo.record_royale_elo(results)
        lb = {row["model"]: row for row in repo.leaderboard()}
        assert set(lb) == {"a", "b", "c"}
        # a beat both b and c -> should have gained ELO; c lost both -> should drop.
        assert lb["a"]["elo"] > 1200
        assert lb["c"]["elo"] < 1200
        # Each model played n-1 = 2 pairwise games in this royale.
        assert lb["a"]["matches"] == 2
