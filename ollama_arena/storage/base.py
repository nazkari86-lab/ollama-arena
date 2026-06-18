"""Repository protocol abstractions for arena persistence."""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class RatingsRepository(Protocol):
    def get(self, model: str) -> float: ...

    def leaderboard(self) -> list[dict]: ...

    def anti_leaderboard(self) -> list[dict]: ...

    def upsert_rating(self, model: str, elo: float, now: float) -> None: ...

    def apply_match_stats(
        self, model_a: str, model_b: str, score_a: float, score_b: float,
    ) -> None: ...

    def record_royale_elo(self, model_results: list[dict]) -> None: ...


@runtime_checkable
class MatchRepository(Protocol):
    def insert_match_log(
        self, model_a: str, model_b: str, category: str,
        score_a: float, score_b: float,
        elo_a_before: float, elo_b_before: float,
        elo_a_after: float, elo_b_after: float, ts: float,
    ) -> None: ...

    def last_match_id(self) -> int: ...

    def match_history(self, limit: int = 50) -> list[dict]: ...

    def recent_matches_summary(self, limit: int = 10) -> list[dict]: ...

    def start_royale(self, category: str, n_models: int, n_tasks: int) -> int: ...

    def save_royale_entry(
        self, royale_id: int, task_id: str, model: str,
        rank: int, score: float, response: str,
        tps: float, latency_s: float,
        instruction: str | None = None,
        hallucination: bool | None = None,
    ) -> None: ...

    def royale_entries(self, royale_id: int) -> list[dict]: ...

    def save_benchmark(
        self, model: str, score: float,
        scores_by_category: dict, n_tasks: int,
    ) -> None: ...

    def benchmark_history(
        self, model: str | None = None, limit: int = 20,
    ) -> list[dict]: ...


@runtime_checkable
class TaskDetailRepository(Protocol):
    def get_cached_response(
        self, model: str, task_id: str, instruction: str,
    ) -> str | None: ...

    def save_task_detail(
        self, match_id: int, task_id: str, category: str,
        difficulty: str, language: str, instruction: str,
        response_a: str, response_b: str, expected: str,
        score_a: float, score_b: float, outcome: str,
        tps_a: float = 0.0, tps_b: float = 0.0,
        latency_a: float = 0.0, latency_b: float = 0.0,
        tool_call_a: str | None = None,
        tool_call_b: str | None = None,
        hallucination_a: bool | None = None,
        hallucination_b: bool | None = None,
    ) -> None: ...

    def tasks_for_match(self, match_id: int) -> list[dict]: ...

    def task_history(self, task_id: str) -> list[dict]: ...

    def category_stats(self, model: str) -> list[dict]: ...
