"""SQLite ratings repository."""
from __future__ import annotations

import logging
import time
from itertools import combinations

from ..base import RatingsRepository
from ._conn import read_conn, write_conn
from .migrations import apply_migrations

log = logging.getLogger("arena.storage.ratings")

_DEFAULT_ELO = 1200


class SqliteRatingsRepository:
    """Persistent ELO ratings in SQLite."""

    def __init__(self, db_path: str = "arena.db"):
        self.db = db_path
        apply_migrations(self.db)

    def get(self, model: str) -> float:
        try:
            with read_conn(self.db) as cx:
                row = cx.execute(
                    "SELECT elo FROM ratings WHERE model=?", (model,),
                ).fetchone()
                return row[0] if row else _DEFAULT_ELO
        except Exception as e:
            log.error(f"Error fetching elo for {model}: {e}")
            return _DEFAULT_ELO

    def upsert_rating(self, model: str, elo: float, now: float) -> None:
        with write_conn(self.db) as cx:
            cx.execute("""
                INSERT INTO ratings(model, elo, wins, losses, draws, matches, updated_at)
                VALUES (?, ?, 0, 0, 0, 0, ?)
                ON CONFLICT(model) DO UPDATE SET
                    elo=excluded.elo, updated_at=excluded.updated_at
            """, (model, elo, now))

    def apply_match_stats(
        self, model_a: str, model_b: str, score_a: float, score_b: float,
    ) -> None:
        with write_conn(self.db) as cx:
            if score_a > score_b:
                cx.execute(
                    "UPDATE ratings SET wins=wins+1, matches=matches+1 WHERE model=?",
                    (model_a,),
                )
                cx.execute(
                    "UPDATE ratings SET losses=losses+1, matches=matches+1 WHERE model=?",
                    (model_b,),
                )
            elif score_b > score_a:
                cx.execute(
                    "UPDATE ratings SET losses=losses+1, matches=matches+1 WHERE model=?",
                    (model_a,),
                )
                cx.execute(
                    "UPDATE ratings SET wins=wins+1, matches=matches+1 WHERE model=?",
                    (model_b,),
                )
            else:
                cx.execute(
                    "UPDATE ratings SET draws=draws+1, matches=matches+1 WHERE model=?",
                    (model_a,),
                )
                cx.execute(
                    "UPDATE ratings SET draws=draws+1, matches=matches+1 WHERE model=?",
                    (model_b,),
                )

    def leaderboard(self) -> list[dict]:
        try:
            with read_conn(self.db) as cx:
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
        except Exception as e:
            log.error(f"Error fetching leaderboard: {e}")
            return []

    def anti_leaderboard(self) -> list[dict]:
        try:
            with read_conn(self.db) as cx:
                rows = cx.execute("""
                    SELECT model, SUM(hallucinations) as total_halluc, SUM(total) as total_checked
                    FROM (
                        SELECT m.model_a as model, SUM(d.hallucination_a) as hallucinations,
                               COUNT(d.hallucination_a) as total
                        FROM task_detail d JOIN match_log m ON m.id = d.match_id
                        WHERE d.hallucination_a IS NOT NULL GROUP BY m.model_a
                        UNION ALL
                        SELECT m.model_b as model, SUM(d.hallucination_b) as hallucinations,
                               COUNT(d.hallucination_b) as total
                        FROM task_detail d JOIN match_log m ON m.id = d.match_id
                        WHERE d.hallucination_b IS NOT NULL GROUP BY m.model_b
                        UNION ALL
                        SELECT model, SUM(hallucination) as hallucinations,
                               COUNT(hallucination) as total
                        FROM royale_entries WHERE hallucination IS NOT NULL GROUP BY model
                    )
                    GROUP BY model
                    HAVING total_checked > 0
                    ORDER BY (CAST(total_halluc AS REAL) / total_checked) DESC,
                             total_checked DESC
                """).fetchall()
            result = []
            for i, (model, halluc, total) in enumerate(rows):
                hr = halluc / max(total, 1)
                result.append({
                    "rank": i + 1, "model": model, "hallucinations": int(halluc),
                    "total_checked": total, "halluc_rate": round(hr, 3),
                })
            return result
        except Exception as e:
            log.error(f"Error fetching anti-leaderboard: {e}")
            return []

    def record_royale_elo(self, model_results: list[dict]) -> None:
        """Update ELO from all pairwise combinations in a royale task."""
        from ollama_arena.elo import update_elo as update_elo_fn

        now = time.time()
        models = [r["model"] for r in model_results]
        current_ratings = {m: self.get(m) for m in models}
        results_map = {m: [] for m in models}
        stats_map = {m: {"wins": 0, "losses": 0, "draws": 0} for m in models}

        for res_a, res_b in combinations(model_results, 2):
            ma, mb = res_a["model"], res_b["model"]
            sa, sb = res_a["score"], res_b["score"]
            ra = current_ratings[ma]
            rb = current_ratings[mb]
            outcome = 1.0 if sa > sb else (0.0 if sb > sa else 0.5)
            new_ra, new_rb = update_elo_fn(ra, rb, outcome)
            results_map[ma].append(new_ra - ra)
            results_map[mb].append(new_rb - rb)
            if outcome == 1.0:
                stats_map[ma]["wins"] += 1
                stats_map[mb]["losses"] += 1
            elif outcome == 0.0:
                stats_map[ma]["losses"] += 1
                stats_map[mb]["wins"] += 1
            else:
                stats_map[ma]["draws"] += 1
                stats_map[mb]["draws"] += 1

        with write_conn(self.db) as cx:
            for m in models:
                final_delta = sum(results_map[m])
                final_elo = current_ratings[m] + final_delta
                s = stats_map[m]
                cx.execute("""
                    INSERT INTO ratings(model, elo, wins, losses, draws, matches, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(model) DO UPDATE SET
                        elo = excluded.elo,
                        wins = wins + excluded.wins,
                        losses = losses + excluded.losses,
                        draws = draws + excluded.draws,
                        matches = matches + excluded.matches,
                        updated_at = excluded.updated_at
                """, (m, final_elo, s["wins"], s["losses"], s["draws"], len(models) - 1, now))
