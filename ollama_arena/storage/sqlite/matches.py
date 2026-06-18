"""SQLite match and royale repository."""
from __future__ import annotations

import json
import logging
import time

from ._conn import read_conn, write_conn

log = logging.getLogger("arena.storage.matches")


class SqliteMatchRepository:
    """Match log, royale, and benchmark persistence."""

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

    def insert_match_log(
        self, model_a: str, model_b: str, category: str,
        score_a: float, score_b: float,
        elo_a_before: float, elo_b_before: float,
        elo_a_after: float, elo_b_after: float, ts: float,
    ) -> None:
        with write_conn(self.db) as cx:
            cx.execute("""
                INSERT INTO match_log
                (model_a,model_b,category,score_a,score_b,
                 elo_a_before,elo_b_before,elo_a_after,elo_b_after,ts)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (model_a, model_b, category, score_a, score_b,
                  elo_a_before, elo_b_before, elo_a_after, elo_b_after, ts))

    def last_match_id(self) -> int:
        try:
            with read_conn(self.db) as cx:
                row = cx.execute("SELECT MAX(id) FROM match_log").fetchone()
                return row[0] or 0
        except Exception as e:
            log.error(f"Error fetching last match id: {e}")
            return 0

    def match_history(self, limit: int = 50) -> list[dict]:
        try:
            with read_conn(self.db) as cx:
                rows = cx.execute("""
                    SELECT id, model_a, model_b, category, score_a, score_b,
                           elo_a_before, elo_b_before, elo_a_after, elo_b_after, ts
                    FROM match_log ORDER BY ts DESC LIMIT ?
                """, (limit,)).fetchall()
            keys = ["id", "model_a", "model_b", "category", "score_a", "score_b",
                    "elo_a_before", "elo_b_before", "elo_a_after", "elo_b_after", "ts"]
            return [dict(zip(keys, r)) for r in rows]
        except Exception as e:
            log.error(f"Error fetching match history: {e}")
            return []

    def recent_matches_summary(self, limit: int = 10) -> list[dict]:
        try:
            with read_conn(self.db) as cx:
                rows = cx.execute("""
                    SELECT m.id, m.model_a, m.model_b, m.category, m.ts,
                           COUNT(d.id) as tasks,
                           SUM(CASE WHEN d.outcome='a_wins' THEN 1 ELSE 0 END) a_wins,
                           SUM(CASE WHEN d.outcome='b_wins' THEN 1 ELSE 0 END) b_wins,
                           SUM(CASE WHEN d.outcome='draw'   THEN 1 ELSE 0 END) draws
                    FROM match_log m
                    LEFT JOIN task_detail d ON d.match_id = m.id
                    GROUP BY m.id
                    ORDER BY m.ts DESC LIMIT ?
                """, (limit,)).fetchall()
            result = []
            for r in rows:
                mid, ma, mb, cat, ts, tasks, aw, bw, dr = r
                winner = ma if aw > bw else (mb if bw > aw else "draw")
                result.append({
                    "id": mid, "model_a": ma, "model_b": mb, "category": cat,
                    "ts": ts, "tasks": tasks,
                    "a_wins": aw, "b_wins": bw, "draws": dr, "winner": winner,
                })
            return result
        except Exception as e:
            log.error(f"Error fetching recent matches summary: {e}")
            return []

    def start_royale(self, category: str, n_models: int, n_tasks: int) -> int:
        try:
            with write_conn(self.db) as cx:
                cx.execute("""
                    INSERT INTO royale_log (category, n_models, n_tasks, ts)
                    VALUES (?, ?, ?, ?)
                """, (category, n_models, n_tasks, time.time()))
                return cx.execute("SELECT last_insert_rowid()").fetchone()[0]
        except Exception as e:
            log.error(f"Error starting royale: {e}")
            return 0

    def save_royale_entry(
        self, royale_id: int, task_id: str, model: str,
        rank: int, score: float, response: str,
        tps: float, latency_s: float,
        instruction: str | None = None,
        hallucination: bool | None = None,
    ) -> None:
        try:
            cols = self._get_table_cols("royale_entries")
            with write_conn(self.db) as cx:
                base = [
                    "royale_id", "task_id", "model", "rank", "score", "response",
                    "tps", "latency_s", "ts",
                ]
                vals = [
                    royale_id, task_id, model, rank, score, response,
                    tps, latency_s, time.time(),
                ]
                if "instruction" in cols and instruction:
                    base.append("instruction")
                    vals.append(instruction)
                if "hallucination" in cols:
                    base.append("hallucination")
                    vals.append(
                        1 if hallucination is True else (
                            0 if hallucination is False else None
                        )
                    )
                placeholders = ",".join("?" * len(base))
                cx.execute(
                    f"INSERT INTO royale_entries ({','.join(base)}) "
                    f"VALUES ({placeholders})",
                    vals,
                )
        except Exception as e:
            log.error(f"Error saving royale entry: {e}")

    def royale_entries(self, royale_id: int) -> list[dict]:
        try:
            with read_conn(self.db) as cx:
                rows = cx.execute("""
                    SELECT task_id, model, rank, score, response, tps, latency_s, ts
                    FROM royale_entries WHERE royale_id=? ORDER BY task_id, rank
                """, (royale_id,)).fetchall()
                keys = [
                    "task_id", "model", "rank", "score", "response",
                    "tps", "latency_s", "ts",
                ]
                return [dict(zip(keys, r)) for r in rows]
        except Exception as e:
            log.error(f"Error fetching royale entries: {e}")
            return []

    def head_to_head(self, model_a: str, model_b: str) -> dict:
        """Direct match statistics between two models."""
        try:
            with read_conn(self.db) as cx:
                rows = cx.execute("""
                    SELECT
                        SUM(CASE WHEN (model_a=? AND score_a>score_b)
                                   OR (model_b=? AND score_b>score_a) THEN 1 ELSE 0 END) a_wins,
                        SUM(CASE WHEN (model_a=? AND score_b>score_a)
                                   OR (model_b=? AND score_a>score_b) THEN 1 ELSE 0 END) b_wins,
                        SUM(CASE WHEN score_a=score_b THEN 1 ELSE 0 END) draws,
                        COUNT(*) total
                    FROM match_log
                    WHERE (model_a=? AND model_b=?) OR (model_a=? AND model_b=?)
                """, (model_a, model_a, model_a, model_a,
                      model_a, model_b, model_b, model_a)).fetchone()
                a_wins, b_wins, draws, total = rows if rows else (0, 0, 0, 0)

                # Category breakdown
                cat_rows = cx.execute("""
                    SELECT category,
                        SUM(CASE WHEN (model_a=? AND score_a>score_b)
                                   OR (model_b=? AND score_b>score_a) THEN 1 ELSE 0 END) a_wins,
                        SUM(CASE WHEN (model_a=? AND score_b>score_a)
                                   OR (model_b=? AND score_a>score_b) THEN 1 ELSE 0 END) b_wins,
                        SUM(CASE WHEN score_a=score_b THEN 1 ELSE 0 END) draws,
                        COUNT(*) total
                    FROM match_log
                    WHERE (model_a=? AND model_b=?) OR (model_a=? AND model_b=?)
                    GROUP BY category ORDER BY total DESC
                """, (model_a, model_a, model_a, model_a,
                      model_a, model_b, model_b, model_a)).fetchall()

            return {
                "model_a": model_a, "model_b": model_b,
                "total_matches": total or 0,
                "a_wins": a_wins or 0, "b_wins": b_wins or 0, "draws": draws or 0,
                "a_win_rate": round((a_wins or 0) / max(total or 1, 1), 3),
                "by_category": [
                    {"category": r[0], "a_wins": r[1], "b_wins": r[2],
                     "draws": r[3], "total": r[4]}
                    for r in cat_rows
                ],
            }
        except Exception as e:
            log.error(f"Error fetching head-to-head {model_a} vs {model_b}: {e}")
            return {"model_a": model_a, "model_b": model_b, "total_matches": 0,
                    "a_wins": 0, "b_wins": 0, "draws": 0, "a_win_rate": 0.5,
                    "by_category": []}

    def arena_stats(self) -> dict:
        """Aggregate stats across the entire arena."""
        try:
            with read_conn(self.db) as cx:
                total = cx.execute("SELECT COUNT(*) FROM match_log").fetchone()[0] or 0
                total_tasks = cx.execute("SELECT COUNT(*) FROM task_detail").fetchone()[0] or 0
                categories = cx.execute(
                    "SELECT COUNT(DISTINCT category) FROM match_log"
                ).fetchone()[0] or 0
                models = cx.execute(
                    "SELECT COUNT(DISTINCT model) FROM ratings"
                ).fetchone()[0] or 0
                most_active = cx.execute("""
                    SELECT model FROM ratings ORDER BY matches DESC LIMIT 1
                """).fetchone()
                last_match = cx.execute(
                    "SELECT MAX(ts) FROM match_log"
                ).fetchone()[0]
            return {
                "total_matches": total,
                "total_tasks_evaluated": total_tasks,
                "categories_covered": categories,
                "models_ranked": models,
                "most_active_model": most_active[0] if most_active else None,
                "last_match_ts": last_match,
            }
        except Exception as e:
            log.error(f"Error fetching arena stats: {e}")
            return {}

    def save_benchmark(
        self, model: str, score: float,
        scores_by_category: dict, n_tasks: int,
    ) -> None:
        try:
            with write_conn(self.db) as cx:
                cx.execute("""
                    INSERT INTO benchmark_runs (model, score, scores_by_category, n_tasks, ts)
                    VALUES (?, ?, ?, ?, ?)
                """, (model, score, json.dumps(scores_by_category), n_tasks, time.time()))
        except Exception as e:
            log.error(f"Error saving benchmark for {model}: {e}")

    def benchmark_history(
        self, model: str | None = None, limit: int = 20,
    ) -> list[dict]:
        try:
            with read_conn(self.db) as cx:
                if model:
                    rows = cx.execute("""
                        SELECT model, score, scores_by_category, n_tasks, ts
                        FROM benchmark_runs WHERE model=? ORDER BY ts DESC LIMIT ?
                    """, (model, limit)).fetchall()
                else:
                    rows = cx.execute("""
                        SELECT model, score, scores_by_category, n_tasks, ts
                        FROM benchmark_runs ORDER BY ts DESC LIMIT ?
                    """, (limit,)).fetchall()
            return [
                {"model": r[0], "score": r[1],
                 "scores_by_category": json.loads(r[2]),
                 "n_tasks": r[3], "ts": r[4]}
                for r in rows
            ]
        except Exception as e:
            log.error(f"Error fetching benchmark history: {e}")
            return []
