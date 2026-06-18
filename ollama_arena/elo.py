"""ELO ratings backed by SQLite repositories.

K=32 is the Chess Federation default. We update after every task rather
than every match, which converges faster but is noisier than the standard
formula on short samples.
"""
from __future__ import annotations

import logging
import time

from .storage.sqlite import (
    SqliteMatchRepository,
    SqliteRatingsRepository,
    SqliteTaskDetailRepository,
    apply_migrations,
)

log = logging.getLogger("arena.elo")

_DEFAULT_ELO = 1200
_K_MAX = 32
_K_MIN = 12


def _expected(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400))


def _k_factor(n_games: int) -> float:
    """Dynamic K: high for newcomers, stabilises after ~100 games."""
    return max(_K_MIN, _K_MAX / (1 + n_games / 30))


def update_elo(
    ra: float, rb: float, result: float,
    na: int = 0, nb: int = 0,
) -> tuple[float, float]:
    """`result` is 1.0=A win, 0.5=draw, 0.0=B win. Standard chess formula.

    `na`/`nb` are the number of games each model has already played;
    K decreases as experience accumulates so the rating stabilises.
    """
    ea = _expected(ra, rb)
    ka = _k_factor(na)
    kb = _k_factor(nb)
    new_ra = ra + ka * (result - ea)
    new_rb = rb + kb * ((1 - result) - (1 - ea))
    return round(new_ra, 2), round(new_rb, 2)


class EloStore:
    """Persistent ELO ratings — facade over storage repositories."""

    def __init__(self, db_path: str = "arena.db"):
        self.db = db_path
        apply_migrations(self.db)
        self._ratings = SqliteRatingsRepository(db_path)
        self._matches = SqliteMatchRepository(db_path)
        self._tasks = SqliteTaskDetailRepository(db_path)

    def get(self, model: str) -> float:
        return self._ratings.get(model)

    def get_cached_response(self, model: str, task_id: str, instruction: str) -> str | None:
        return self._tasks.get_cached_response(model, task_id, instruction)

    def _n_games(self, model: str) -> int:
        lb = self._ratings.leaderboard()
        for row in lb:
            if row["model"] == model:
                return row.get("matches", 0)
        return 0

    def record_match(self, model_a: str, model_b: str, category: str,
                     score_a: float, score_b: float) -> tuple[float, float]:
        ra = self.get(model_a)
        rb = self.get(model_b)

        total = score_a + score_b
        if total == 0:
            result = 0.5
        else:
            result = score_a / total

        na = self._n_games(model_a)
        nb = self._n_games(model_b)
        new_ra, new_rb = update_elo(ra, rb, result, na=na, nb=nb)
        now = time.time()

        try:
            self._ratings.upsert_rating(model_a, new_ra, now)
            self._ratings.upsert_rating(model_b, new_rb, now)
            self._ratings.apply_match_stats(model_a, model_b, score_a, score_b)
            self._matches.insert_match_log(
                model_a, model_b, category, score_a, score_b,
                ra, rb, new_ra, new_rb, now,
            )
        except Exception as e:
            log.error(f"Error recording match between {model_a} and {model_b}: {e}")

        # Non-blocking webhook notification (Discord / Slack / custom)
        try:
            from .webhooks import notify_match
            notify_match(
                model_a, model_b, category, score_a, score_b,
                ra, new_ra, rb, new_rb, duration_s=0.0,
            )
        except Exception:
            pass

        return new_ra, new_rb

    def save_task_detail(self, *args, **kwargs):
        return self._tasks.save_task_detail(*args, **kwargs)

    def last_match_id(self) -> int:
        return self._matches.last_match_id()

    def leaderboard(self) -> list[dict]:
        return self._ratings.leaderboard()

    def anti_leaderboard(self) -> list[dict]:
        return self._ratings.anti_leaderboard()

    def match_history(self, limit: int = 50) -> list[dict]:
        return self._matches.match_history(limit)

    def tasks_for_match(self, match_id: int) -> list[dict]:
        return self._tasks.tasks_for_match(match_id)

    def task_history(self, task_id: str) -> list[dict]:
        return self._tasks.task_history(task_id)

    def category_stats(self, model: str) -> list[dict]:
        return self._tasks.category_stats(model)

    def save_benchmark(self, model: str, score: float,
                       scores_by_category: dict, n_tasks: int):
        return self._matches.save_benchmark(model, score, scores_by_category, n_tasks)

    def benchmark_history(self, model: str | None = None, limit: int = 20) -> list[dict]:
        return self._matches.benchmark_history(model, limit)

    def recent_matches_summary(self, limit: int = 10) -> list[dict]:
        return self._matches.recent_matches_summary(limit)

    def start_royale(self, category: str, n_models: int, n_tasks: int) -> int:
        return self._matches.start_royale(category, n_models, n_tasks)

    def save_royale_entry(self, *args, **kwargs):
        return self._matches.save_royale_entry(*args, **kwargs)

    def royale_entries(self, royale_id: int) -> list[dict]:
        return self._matches.royale_entries(royale_id)

    def record_royale_elo(self, model_results: list[dict]):
        return self._ratings.record_royale_elo(model_results)
