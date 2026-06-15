"""ELO rating system with SQLite persistence."""
from __future__ import annotations
import sqlite3, json, time, os, math
from pathlib import Path

_DEFAULT_ELO = 1200
_K = 32


def _expected(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400))


def update_elo(ra: float, rb: float, result: float) -> tuple[float, float]:
    """result: 1.0=A wins, 0.5=draw, 0.0=B wins. Returns (new_ra, new_rb)."""
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
        return sqlite3.connect(self.db)

    def _init_db(self):
        with self._conn() as cx:
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
            """)

    def get(self, model: str) -> float:
        with self._conn() as cx:
            row = cx.execute("SELECT elo FROM ratings WHERE model=?", (model,)).fetchone()
            return row[0] if row else _DEFAULT_ELO

    def record_match(self, model_a: str, model_b: str, category: str,
                     score_a: float, score_b: float):
        """Record match result and update ELO for both models."""
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

        with self._conn() as cx:
            for model, elo in [(model_a, new_ra), (model_b, new_rb)]:
                cx.execute("""
                    INSERT INTO ratings(model, elo, wins, losses, draws, matches, updated_at)
                    VALUES (?, ?, 0, 0, 0, 0, ?)
                    ON CONFLICT(model) DO UPDATE SET
                        elo=excluded.elo, updated_at=excluded.updated_at
                """, (model, elo, now))

            # Update win/loss/draw counters
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
                (model_a,model_b,category,score_a,score_b,elo_a_before,elo_b_before,elo_a_after,elo_b_after,ts)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (model_a, model_b, category, score_a, score_b, ra, rb, new_ra, new_rb, now))

        return new_ra, new_rb

    def leaderboard(self) -> list[dict]:
        with self._conn() as cx:
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

    def match_history(self, limit: int = 50) -> list[dict]:
        with self._conn() as cx:
            rows = cx.execute("""
                SELECT model_a, model_b, category, score_a, score_b,
                       elo_a_before, elo_b_before, elo_a_after, elo_b_after, ts
                FROM match_log ORDER BY ts DESC LIMIT ?
            """, (limit,)).fetchall()
        keys = ["model_a", "model_b", "category", "score_a", "score_b",
                "elo_a_before", "elo_b_before", "elo_a_after", "elo_b_after", "ts"]
        return [dict(zip(keys, r)) for r in rows]
