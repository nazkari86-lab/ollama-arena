"""ELO ratings backed by SQLite.

K=32 is the Chess Federation default. We update after every task rather
than every match, which converges faster but is noisier than the standard
formula on short samples.
"""
from __future__ import annotations
import sqlite3, time
import logging

log = logging.getLogger("arena.elo")

_DEFAULT_ELO = 1200
_K = 32


def _expected(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400))


def update_elo(ra: float, rb: float, result: float) -> tuple[float, float]:
    """`result` is 1.0=A win, 0.5=draw, 0.0=B win. Standard chess formula."""
    ea = _expected(ra, rb)
    new_ra = ra + _K * (result - ea)
    new_rb = rb + _K * ((1 - result) - (1 - ea))
    return round(new_ra, 2), round(new_rb, 2)


class EloStore:
    """Persistent ELO ratings stored in SQLite."""

    def __init__(self, db_path: str = "arena.db"):
        self.db = db_path
        self._init_db()

    def _conn(self):
        # Increased timeout to 30.0s to avoid 'database is locked' errors under high concurrency.
        # isolation_level="IMMEDIATE" ensures write locks are acquired safely, preventing deadlocks.
        return sqlite3.connect(self.db, timeout=30.0, isolation_level="IMMEDIATE")

    def _init_db(self):
        with self._conn() as cx:
            # Enable WAL mode for high concurrency
            cx.execute("PRAGMA journal_mode=WAL;")
            cx.execute("PRAGMA synchronous=NORMAL;")
            cx.executescript("""
                CREATE TABLE IF NOT EXISTS ratings (
                    model TEXT PRIMARY KEY,
                    elo   REAL DEFAULT 1200,
                    wins  INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    draws INTEGER DEFAULT 0,
                    matches INTEGER DEFAULT 0,
                    updated_at REAL
                );
                CREATE TABLE IF NOT EXISTS match_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_a TEXT,
                    model_b TEXT,
                    category TEXT,
                    score_a REAL,
                    score_b REAL,
                    elo_a_before REAL,
                    elo_b_before REAL,
                    elo_a_after REAL,
                    elo_b_after REAL,
                    ts REAL
                );
                CREATE TABLE IF NOT EXISTS task_detail (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id INTEGER,
                    task_id TEXT,
                    category TEXT,
                    difficulty TEXT,
                    language TEXT,
                    instruction TEXT,
                    response_a TEXT,
                    response_b TEXT,
                    expected TEXT,
                    score_a REAL,
                    score_b REAL,
                    outcome TEXT,
                    tps_a REAL,
                    tps_b REAL,
                    latency_a REAL,
                    latency_b REAL,
                    ts REAL
                );
                CREATE INDEX IF NOT EXISTS idx_task_detail_task
                    ON task_detail(task_id);
                CREATE INDEX IF NOT EXISTS idx_task_detail_match
                    ON task_detail(match_id);
                CREATE TABLE IF NOT EXISTS benchmark_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model TEXT,
                    score REAL,
                    scores_by_category TEXT,
                    n_tasks INTEGER,
                    ts REAL
                );
            """)

    def get(self, model: str) -> float:
        try:
            with self._conn() as cx:
                row = cx.execute("SELECT elo FROM ratings WHERE model=?", (model,)).fetchone()
                return row[0] if row else _DEFAULT_ELO
        except sqlite3.Error as e:
            log.error(f"Error fetching elo for {model}: {e}")
            return _DEFAULT_ELO

    def get_cached_response(self, model: str, task_id: str, instruction: str) -> str | None:
        try:
            with sqlite3.connect(self.db, timeout=30.0) as cx:
                # Optimized single query using UNION ALL for better caching performance
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
        except sqlite3.Error as e:
            log.error(f"Error fetching cached response for {model}: {e}")
        return None

    def record_match(self, model_a: str, model_b: str, category: str,
                     score_a: float, score_b: float) -> tuple[float, float]:
        ra = self.get(model_a)
        rb = self.get(model_b)

        if score_a > score_b:
            result = 1.0
        elif score_b > score_a:
            result = 0.0
        else:
            result = 0.5

        new_ra, new_rb = update_elo(ra, rb, result)
        now = time.time()

        try:
            with self._conn() as cx:
                for model, elo in [(model_a, new_ra), (model_b, new_rb)]:
                    cx.execute("""
                        INSERT INTO ratings(model, elo, wins, losses, draws, matches, updated_at)
                        VALUES (?, ?, 0, 0, 0, 0, ?)
                        ON CONFLICT(model) DO UPDATE SET
                            elo=excluded.elo, updated_at=excluded.updated_at
                    """, (model, elo, now))

                if result == 1.0:
                    cx.execute("UPDATE ratings SET wins=wins+1, matches=matches+1 WHERE model=?", (model_a,))
                    cx.execute("UPDATE ratings SET losses=losses+1, matches=matches+1 WHERE model=?", (model_b,))
                elif result == 0.0:
                    cx.execute("UPDATE ratings SET losses=losses+1, matches=matches+1 WHERE model=?", (model_a,))
                    cx.execute("UPDATE ratings SET wins=wins+1, matches=matches+1 WHERE model=?", (model_b,))
                else:
                    cx.execute("UPDATE ratings SET draws=draws+1, matches=matches+1 WHERE model=?", (model_a,))
                    cx.execute("UPDATE ratings SET draws=draws+1, matches=matches+1 WHERE model=?", (model_b,))

                cx.execute("""
                    INSERT INTO match_log
                    (model_a,model_b,category,score_a,score_b,
                     elo_a_before,elo_b_before,elo_a_after,elo_b_after,ts)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                """, (model_a, model_b, category, score_a, score_b,
                      ra, rb, new_ra, new_rb, now))
        except sqlite3.Error as e:
            log.error(f"Error recording match between {model_a} and {model_b}: {e}")

        return new_ra, new_rb

    def save_task_detail(
        self, match_id: int, task_id: str, category: str,
        difficulty: str, language: str, instruction: str,
        response_a: str, response_b: str, expected: str,
        score_a: float, score_b: float, outcome: str,
        tps_a: float = 0.0, tps_b: float = 0.0,
        latency_a: float = 0.0, latency_b: float = 0.0,
    ):
        try:
            with self._conn() as cx:
                cx.execute("""
                    INSERT INTO task_detail
                    (match_id, task_id, category, difficulty, language,
                     instruction, response_a, response_b, expected,
                     score_a, score_b, outcome, tps_a, tps_b, latency_a, latency_b, ts)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (match_id, task_id, category, difficulty, language,
                      instruction, response_a, response_b, expected,
                      score_a, score_b, outcome, tps_a, tps_b, latency_a, latency_b,
                      time.time()))
        except sqlite3.Error as e:
            log.error(f"Error saving task detail for {task_id}: {e}")

    def last_match_id(self) -> int:
        try:
            with sqlite3.connect(self.db, timeout=30.0) as cx:
                row = cx.execute("SELECT MAX(id) FROM match_log").fetchone()
                return row[0] or 0
        except sqlite3.Error as e:
            log.error(f"Error fetching last match id: {e}")
            return 0

    def leaderboard(self) -> list[dict]:
        try:
            with sqlite3.connect(self.db, timeout=30.0) as cx:
                rows = cx.execute("""
                    SELECT model, elo, wins, losses, draws, matches
                    FROM ratings ORDER BY elo DESC
                """).fetchall()
            result = []
            for i, (model, elo, wins, losses, draws, matches) in enumerate(rows):
                wr = wins / max(matches, 1)
                result.append({
                    "rank": i + 1, "model": model, "elo": round(elo, 1),
                    "wins": wins, "losses": losses, "draws": draws,
                    "matches": matches, "win_rate": round(wr, 3),
                })
            return result
        except sqlite3.Error as e:
            log.error(f"Error fetching leaderboard: {e}")
            return []

    def match_history(self, limit: int = 50) -> list[dict]:
        try:
            with sqlite3.connect(self.db, timeout=30.0) as cx:
                rows = cx.execute("""
                    SELECT id, model_a, model_b, category, score_a, score_b,
                           elo_a_before, elo_b_before, elo_a_after, elo_b_after, ts
                    FROM match_log ORDER BY ts DESC LIMIT ?
                """, (limit,)).fetchall()
            keys = ["id", "model_a", "model_b", "category", "score_a", "score_b",
                    "elo_a_before", "elo_b_before", "elo_a_after", "elo_b_after", "ts"]
            return [dict(zip(keys, r)) for r in rows]
        except sqlite3.Error as e:
            log.error(f"Error fetching match history: {e}")
            return []

    def tasks_for_match(self, match_id: int) -> list[dict]:
        try:
            with sqlite3.connect(self.db, timeout=30.0) as cx:
                rows = cx.execute("""
                    SELECT task_id, category, difficulty, language, instruction,
                           response_a, response_b, expected,
                           score_a, score_b, outcome, tps_a, tps_b, latency_a, latency_b, ts
                    FROM task_detail WHERE match_id=? ORDER BY ts
                """, (match_id,)).fetchall()
            keys = ["task_id", "category", "difficulty", "language", "instruction",
                    "response_a", "response_b", "expected",
                    "score_a", "score_b", "outcome", "tps_a", "tps_b",
                    "latency_a", "latency_b", "ts"]
            return [dict(zip(keys, r)) for r in rows]
        except sqlite3.Error as e:
            log.error(f"Error fetching tasks for match {match_id}: {e}")
            return []

    def task_history(self, task_id: str) -> list[dict]:
        try:
            with sqlite3.connect(self.db, timeout=30.0) as cx:
                rows = cx.execute("""
                    SELECT d.task_id, d.category, d.difficulty,
                           m.model_a, m.model_b,
                           d.instruction, d.response_a, d.response_b, d.expected,
                           d.score_a, d.score_b, d.outcome, d.ts
                    FROM task_detail d
                    JOIN match_log m ON m.id = d.match_id
                    WHERE d.task_id=? ORDER BY d.ts DESC
                """, (task_id,)).fetchall()
            keys = ["task_id", "category", "difficulty", "model_a", "model_b",
                    "instruction", "response_a", "response_b", "expected",
                    "score_a", "score_b", "outcome", "ts"]
            return [dict(zip(keys, r)) for r in rows]
        except sqlite3.Error as e:
            log.error(f"Error fetching task history for {task_id}: {e}")
            return []

    def category_stats(self, model: str) -> list[dict]:
        """Per-category win/loss breakdown for a single model."""
        try:
            with sqlite3.connect(self.db, timeout=30.0) as cx:
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
                {"category": r[0], "wins": r[1], "losses": r[2],
                 "draws": r[3], "total": r[4],
                 "win_rate": round(r[1] / max(r[4], 1), 3)}
                for r in rows
            ]
        except sqlite3.Error as e:
            log.error(f"Error fetching category stats for {model}: {e}")
            return []

    def save_benchmark(self, model: str, score: float,
                       scores_by_category: dict, n_tasks: int):
        import json
        try:
            with self._conn() as cx:
                cx.execute("""
                    INSERT INTO benchmark_runs (model, score, scores_by_category, n_tasks, ts)
                    VALUES (?, ?, ?, ?, ?)
                """, (model, score, json.dumps(scores_by_category), n_tasks, time.time()))
        except sqlite3.Error as e:
            log.error(f"Error saving benchmark for {model}: {e}")

    def benchmark_history(self, model: str | None = None, limit: int = 20) -> list[dict]:
        import json
        try:
            with sqlite3.connect(self.db, timeout=30.0) as cx:
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
        except sqlite3.Error as e:
            log.error(f"Error fetching benchmark history: {e}")
            return []

    def recent_matches_summary(self, limit: int = 10) -> list[dict]:
        """Match-level summary: models, category, task count, winner."""
        try:
            with sqlite3.connect(self.db, timeout=30.0) as cx:
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
        except sqlite3.Error as e:
            log.error(f"Error fetching recent matches summary: {e}")
            return []
