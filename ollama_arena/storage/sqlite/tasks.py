"""SQLite task detail repository."""
from __future__ import annotations

import logging
import time

from ..base import TaskDetailRepository
from ._conn import read_conn, write_conn

log = logging.getLogger("arena.storage.tasks")


class SqliteTaskDetailRepository:
    """Task-level match detail persistence."""

    def __init__(self, db_path: str = "arena.db"):
        self.db = db_path
        self._column_cache: dict[str, set[str]] = {}

    def _get_table_cols(self, table_name: str) -> set[str]:
        if table_name in self._column_cache:
            return self._column_cache[table_name]
        try:
            with read_conn(self.db) as cx:
                cols = {r[1] for r in cx.execute(f"PRAGMA table_info({table_name})")}
                self._column_cache[table_name] = cols
                return cols
        except Exception as e:
            log.error(f"Error fetching columns for {table_name}: {e}")
            return set()

    def get_cached_response(
        self, model: str, task_id: str, instruction: str,
    ) -> str | None:
        try:
            with read_conn(self.db) as cx:
                row = cx.execute("""
                    SELECT response FROM (
                        SELECT d.response_a as response, d.ts
                        FROM task_detail d
                        JOIN match_log m ON m.id = d.match_id
                        WHERE m.model_a=? AND d.task_id=? AND d.instruction=?

                        UNION ALL

                        SELECT d.response_b as response, d.ts
                        FROM task_detail d
                        JOIN match_log m ON m.id = d.match_id
                        WHERE m.model_b=? AND d.task_id=? AND d.instruction=?
                    )
                    ORDER BY ts DESC LIMIT 1
                """, (model, task_id, instruction, model, task_id, instruction)).fetchone()
                if row and row[0]:
                    return row[0]
        except Exception as e:
            log.error(f"Error fetching cached response for {model}: {e}")
        return None

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
    ) -> None:
        try:
            cols = self._get_table_cols("task_detail")
            with write_conn(self.db) as cx:
                base = [
                    "match_id", "task_id", "category", "difficulty", "language",
                    "instruction", "response_a", "response_b", "expected",
                    "score_a", "score_b", "outcome",
                    "tps_a", "tps_b", "latency_a", "latency_b", "ts",
                ]
                vals = [
                    match_id, task_id, category, difficulty, language,
                    instruction, response_a, response_b, expected,
                    score_a, score_b, outcome,
                    tps_a, tps_b, latency_a, latency_b, time.time(),
                ]
                if "tool_call_a" in cols:
                    base.extend(["tool_call_a", "tool_call_b"])
                    vals.extend([tool_call_a, tool_call_b])
                if "hallucination_a" in cols:
                    base.extend(["hallucination_a", "hallucination_b"])
                    vals.extend([
                        1 if hallucination_a is True else (0 if hallucination_a is False else None),
                        1 if hallucination_b is True else (0 if hallucination_b is False else None),
                    ])
                placeholders = ",".join("?" * len(base))
                cx.execute(
                    f"INSERT INTO task_detail ({','.join(base)}) VALUES ({placeholders})",
                    vals,
                )
        except Exception as e:
            log.error(f"Error saving task detail for {task_id}: {e}")

    def tasks_for_match(self, match_id: int) -> list[dict]:
        try:
            with read_conn(self.db) as cx:
                cols = {r[1] for r in cx.execute("PRAGMA table_info(task_detail)")}
                select = [
                    "task_id", "category", "difficulty", "language", "instruction",
                    "response_a", "response_b", "expected",
                    "score_a", "score_b", "outcome",
                    "tps_a", "tps_b", "latency_a", "latency_b", "ts",
                ]
                if "tool_call_a" in cols:
                    select.extend(["tool_call_a", "tool_call_b"])
                rows = cx.execute(
                    f"SELECT {','.join(select)} FROM task_detail "
                    "WHERE match_id=? ORDER BY ts",
                    (match_id,),
                ).fetchall()
            return [dict(zip(select, r)) for r in rows]
        except Exception as e:
            log.error(f"Error fetching tasks for match {match_id}: {e}")
            return []

    def task_history(self, task_id: str) -> list[dict]:
        try:
            with read_conn(self.db) as cx:
                cols = {r[1] for r in cx.execute("PRAGMA table_info(task_detail)")}
                extra_select = ""
                extra_keys: list[str] = []
                if "tool_call_a" in cols:
                    extra_select = ", d.tool_call_a, d.tool_call_b"
                    extra_keys = ["tool_call_a", "tool_call_b"]
                rows = cx.execute(f"""
                    SELECT d.task_id, d.category, d.difficulty,
                           m.model_a, m.model_b,
                           d.instruction, d.response_a, d.response_b, d.expected,
                           d.score_a, d.score_b, d.outcome, d.ts{extra_select}
                    FROM task_detail d
                    JOIN match_log m ON m.id = d.match_id
                    WHERE d.task_id=? ORDER BY d.ts DESC
                """, (task_id,)).fetchall()
            keys = [
                "task_id", "category", "difficulty", "model_a", "model_b",
                "instruction", "response_a", "response_b", "expected",
                "score_a", "score_b", "outcome", "ts",
            ] + extra_keys
            return [dict(zip(keys, r)) for r in rows]
        except Exception as e:
            log.error(f"Error fetching task history for {task_id}: {e}")
            return []

    def category_stats(self, model: str) -> list[dict]:
        try:
            with read_conn(self.db) as cx:
                rows = cx.execute("""
                    SELECT d.category,
                           SUM(CASE WHEN (m.model_a=? AND d.outcome='a_wins')
                                      OR (m.model_b=? AND d.outcome='b_wins') THEN 1 ELSE 0 END) wins,
                           SUM(CASE WHEN (m.model_a=? AND d.outcome='b_wins')
                                      OR (m.model_b=? AND d.outcome='a_wins') THEN 1 ELSE 0 END) losses,
                           SUM(CASE WHEN d.outcome='draw' THEN 1 ELSE 0 END) draws,
                           COUNT(*) total
                    FROM task_detail d
                    JOIN match_log m ON m.id = d.match_id
                    WHERE m.model_a=? OR m.model_b=?
                    GROUP BY d.category
                    ORDER BY total DESC
                """, (model, model, model, model, model, model)).fetchall()
            return [
                {
                    "category": r[0], "wins": r[1], "losses": r[2],
                    "draws": r[3], "total": r[4],
                    "win_rate": round(r[1] / max(r[4], 1), 3),
                }
                for r in rows
            ]
        except Exception as e:
            log.error(f"Error fetching category stats for {model}: {e}")
            return []
