"""Tests for storage/sqlite/matches.py — SqliteMatchRepository."""
from __future__ import annotations

import json
import time
import pytest


@pytest.fixture
def db_path(tmp_path):
    """Create a fully-migrated temp SQLite DB."""
    from ollama_arena.storage.sqlite.migrations import apply_migrations
    path = str(tmp_path / "test_arena.db")
    apply_migrations(path)
    return path


@pytest.fixture
def repo(db_path):
    from ollama_arena.storage.sqlite.matches import SqliteMatchRepository
    return SqliteMatchRepository(db_path=db_path)


# ──────────────────────────────────────────────────────────────────────────────
# insert_match_log + match_history + last_match_id
# ──────────────────────────────────────────────────────────────────────────────

class TestInsertMatchLog:
    def test_insert_and_history(self, repo):
        repo.insert_match_log("a", "b", "coding", 0.8, 0.6, 1200, 1200, 1210, 1190, time.time())
        history = repo.match_history(limit=10)
        assert len(history) == 1
        assert history[0]["model_a"] == "a"
        assert history[0]["model_b"] == "b"
        assert history[0]["category"] == "coding"

    def test_last_match_id_empty(self, repo):
        assert repo.last_match_id() == 0

    def test_last_match_id_after_insert(self, repo):
        repo.insert_match_log("a", "b", "math", 1.0, 0.0, 1200, 1200, 1230, 1170, time.time())
        assert repo.last_match_id() >= 1

    def test_match_history_limit(self, repo):
        for i in range(5):
            repo.insert_match_log("a", "b", "coding", 0.5, 0.5, 1200, 1200, 1200, 1200, time.time())
        assert len(repo.match_history(limit=3)) == 3

    def test_match_history_empty(self, repo):
        assert repo.match_history() == []


# ──────────────────────────────────────────────────────────────────────────────
# recent_matches_summary
# ──────────────────────────────────────────────────────────────────────────────

class TestRecentMatchesSummary:
    def test_empty(self, repo):
        assert repo.recent_matches_summary() == []

    def test_with_match(self, repo, db_path):
        import sqlite3
        repo.insert_match_log("alpha", "beta", "reasoning", 0.9, 0.4, 1200, 1200, 1220, 1180, time.time())
        mid = repo.last_match_id()
        # Insert task_detail so summary has tasks
        cx = sqlite3.connect(db_path)
        cx.execute(
            "INSERT INTO task_detail (match_id, outcome) VALUES (?, ?)", (mid, "a_wins")
        )
        cx.commit()
        cx.close()
        summary = repo.recent_matches_summary(limit=5)
        assert len(summary) >= 1
        assert summary[0]["model_a"] == "alpha"

    def test_winner_determination_a(self, repo, db_path):
        import sqlite3
        repo.insert_match_log("a", "b", "coding", 0.9, 0.4, 1200, 1200, 1220, 1180, time.time())
        mid = repo.last_match_id()
        cx = sqlite3.connect(db_path)
        cx.execute("INSERT INTO task_detail (match_id, outcome) VALUES (?, 'a_wins')", (mid,))
        cx.commit()
        cx.close()
        summary = repo.recent_matches_summary(limit=1)
        assert summary[0]["winner"] == "a"

    def test_winner_determination_draw(self, repo, db_path):
        import sqlite3
        repo.insert_match_log("a", "b", "coding", 0.5, 0.5, 1200, 1200, 1200, 1200, time.time())
        mid = repo.last_match_id()
        cx = sqlite3.connect(db_path)
        cx.execute("INSERT INTO task_detail (match_id, outcome) VALUES (?, 'draw')", (mid,))
        cx.commit()
        cx.close()
        summary = repo.recent_matches_summary(limit=1)
        assert summary[0]["winner"] == "draw"


# ──────────────────────────────────────────────────────────────────────────────
# Royale
# ──────────────────────────────────────────────────────────────────────────────

class TestRoyale:
    def test_start_royale_returns_id(self, repo):
        rid = repo.start_royale("math", 4, 10)
        assert rid >= 1

    def test_save_royale_entry_and_retrieve(self, repo):
        rid = repo.start_royale("coding", 3, 5)
        repo.save_royale_entry(rid, "task_1", "phi-4", 1, 0.9, "response", 50.0, 0.5)
        entries = repo.royale_entries(rid)
        assert len(entries) == 1
        assert entries[0]["model"] == "phi-4"
        assert entries[0]["score"] == pytest.approx(0.9)

    def test_save_royale_entry_with_instruction(self, repo):
        rid = repo.start_royale("coding", 2, 3)
        repo.save_royale_entry(
            rid, "task_1", "qwen", 2, 0.7, "resp", 40.0, 0.8,
            instruction="Write a function", hallucination=False,
        )
        entries = repo.royale_entries(rid)
        assert len(entries) == 1

    def test_save_royale_entry_hallucination_none(self, repo):
        rid = repo.start_royale("math", 2, 2)
        repo.save_royale_entry(
            rid, "task_1", "mistral", 1, 0.8, "resp", 45.0, 0.3,
            hallucination=None,
        )
        entries = repo.royale_entries(rid)
        assert len(entries) == 1

    def test_royale_entries_empty(self, repo):
        rid = repo.start_royale("coding", 2, 3)
        assert repo.royale_entries(rid) == []

    def test_royale_entries_wrong_id(self, repo):
        assert repo.royale_entries(99999) == []


# ──────────────────────────────────────────────────────────────────────────────
# head_to_head
# ──────────────────────────────────────────────────────────────────────────────

class TestHeadToHead:
    def test_empty_head_to_head(self, repo):
        result = repo.head_to_head("alpha", "beta")
        assert result["total_matches"] == 0
        assert result["a_wins"] == 0

    def test_head_to_head_with_matches(self, repo):
        repo.insert_match_log("alpha", "beta", "coding", 0.9, 0.4, 1200, 1200, 1220, 1180, time.time())
        repo.insert_match_log("alpha", "beta", "math", 0.3, 0.8, 1200, 1200, 1190, 1210, time.time())
        result = repo.head_to_head("alpha", "beta")
        assert result["total_matches"] == 2
        assert result["a_wins"] + result["b_wins"] + result["draws"] == result["total_matches"]

    def test_head_to_head_reverse_order(self, repo):
        repo.insert_match_log("beta", "alpha", "coding", 0.9, 0.4, 1200, 1200, 1220, 1180, time.time())
        result = repo.head_to_head("alpha", "beta")
        assert result["total_matches"] == 1

    def test_win_rate_in_range(self, repo):
        repo.insert_match_log("alpha", "beta", "coding", 0.9, 0.4, 1200, 1200, 1220, 1180, time.time())
        result = repo.head_to_head("alpha", "beta")
        assert 0.0 <= result["a_win_rate"] <= 1.0

    def test_by_category_populated(self, repo):
        repo.insert_match_log("alpha", "beta", "coding", 0.9, 0.4, 1200, 1200, 1220, 1180, time.time())
        result = repo.head_to_head("alpha", "beta")
        assert len(result["by_category"]) >= 1
        assert result["by_category"][0]["category"] == "coding"


# ──────────────────────────────────────────────────────────────────────────────
# arena_stats
# ──────────────────────────────────────────────────────────────────────────────

class TestArenaStats:
    def test_empty_stats(self, repo):
        result = repo.arena_stats()
        assert result["total_matches"] == 0

    def test_stats_after_matches(self, repo, db_path):
        import sqlite3
        repo.insert_match_log("a", "b", "coding", 0.8, 0.5, 1200, 1200, 1215, 1185, time.time())
        repo.insert_match_log("c", "d", "math", 0.7, 0.6, 1200, 1200, 1205, 1195, time.time())
        # Insert ratings for models_ranked
        cx = sqlite3.connect(db_path)
        cx.execute("INSERT OR IGNORE INTO ratings (model, elo, matches) VALUES ('a', 1215, 1)")
        cx.execute("INSERT OR IGNORE INTO ratings (model, elo, matches) VALUES ('b', 1185, 1)")
        cx.commit()
        cx.close()
        result = repo.arena_stats()
        assert result["total_matches"] == 2
        assert result["categories_covered"] == 2
        assert result["models_ranked"] >= 2

    def test_stats_last_match_ts(self, repo):
        ts = time.time()
        repo.insert_match_log("a", "b", "coding", 1.0, 0.0, 1200, 1200, 1230, 1170, ts)
        result = repo.arena_stats()
        assert result["last_match_ts"] is not None


# ──────────────────────────────────────────────────────────────────────────────
# benchmark_history
# ──────────────────────────────────────────────────────────────────────────────

class TestBenchmarkHistory:
    def test_save_and_retrieve_benchmark(self, repo):
        repo.save_benchmark("phi-4", 0.85, {"coding": 0.9, "math": 0.8}, 100)
        history = repo.benchmark_history()
        assert len(history) == 1
        assert history[0]["model"] == "phi-4"
        assert history[0]["score"] == pytest.approx(0.85)
        assert history[0]["scores_by_category"]["coding"] == pytest.approx(0.9)

    def test_benchmark_history_filtered_by_model(self, repo):
        repo.save_benchmark("phi-4", 0.85, {"coding": 0.9}, 100)
        repo.save_benchmark("qwen", 0.75, {"math": 0.8}, 50)
        history = repo.benchmark_history(model="phi-4")
        assert len(history) == 1
        assert history[0]["model"] == "phi-4"

    def test_benchmark_history_empty(self, repo):
        assert repo.benchmark_history() == []

    def test_benchmark_history_limit(self, repo):
        for i in range(5):
            repo.save_benchmark("phi-4", 0.5 + i * 0.05, {}, 10)
        history = repo.benchmark_history(limit=3)
        assert len(history) == 3


# ──────────────────────────────────────────────────────────────────────────────
# _get_table_cols (column cache)
# ──────────────────────────────────────────────────────────────────────────────

class TestGetTableCols:
    def test_get_cols_match_log(self, repo):
        cols = repo._get_table_cols("match_log")
        assert "model_a" in cols
        assert "model_b" in cols
        assert "category" in cols

    def test_get_cols_cached(self, repo):
        # Call twice to exercise cache path
        cols1 = repo._get_table_cols("match_log")
        cols2 = repo._get_table_cols("match_log")
        assert cols1 == cols2

    def test_get_cols_nonexistent_table(self, repo):
        cols = repo._get_table_cols("nonexistent_table_xyz")
        assert cols == set()
