"""SQLite ratings repository."""
from __future__ import annotations

import logging
import time
from itertools import combinations

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

    def upsert_rating(self, model: str, elo: float, now: float, conn=None) -> None:
        """Insert/update one model's rating.

        `conn` lets a caller (EloStore.record_match) thread a single shared
        connection/transaction through multiple repository calls instead of
        each call committing its own separate transaction — see
        `apply_match_stats` docstring for why that matters. When `conn` is
        omitted this opens its own connection and commits immediately,
        same as before.
        """
        if conn is not None:
            conn.execute("""
                INSERT INTO ratings(model, elo, wins, losses, draws, matches, updated_at)
                VALUES (?, ?, 0, 0, 0, 0, ?)
                ON CONFLICT(model) DO UPDATE SET
                    elo=excluded.elo, updated_at=excluded.updated_at
            """, (model, elo, now))
            return
        with write_conn(self.db) as cx:
            cx.execute("""
                INSERT INTO ratings(model, elo, wins, losses, draws, matches, updated_at)
                VALUES (?, ?, 0, 0, 0, 0, ?)
                ON CONFLICT(model) DO UPDATE SET
                    elo=excluded.elo, updated_at=excluded.updated_at
            """, (model, elo, now))

    def apply_match_stats(
        self, model_a: str, model_b: str, score_a: float, score_b: float,
        conn=None,
    ) -> None:
        """Bump win/loss/draw/matches counters for both models.

        Requires a `ratings` row to already exist for each model (callers
        always run upsert_rating() first — see EloManager.record_match). If
        a row is missing, the UPDATE silently affects 0 rows and the stats
        bump is lost with no error; we log a warning so that failure mode
        is at least visible instead of corrupting data quietly.

        `conn`: optional shared connection (see upsert_rating docstring).
        """
        if conn is not None:
            self._apply_match_stats_on(conn, model_a, model_b, score_a, score_b)
            return
        with write_conn(self.db) as cx:
            self._apply_match_stats_on(cx, model_a, model_b, score_a, score_b)

    def _apply_match_stats_on(self, cx, model_a, model_b, score_a, score_b) -> None:
        if score_a > score_b:
            cur_a = cx.execute(
                "UPDATE ratings SET wins=wins+1, matches=matches+1 WHERE model=?",
                (model_a,),
            )
            cur_b = cx.execute(
                "UPDATE ratings SET losses=losses+1, matches=matches+1 WHERE model=?",
                (model_b,),
            )
        elif score_b > score_a:
            cur_a = cx.execute(
                "UPDATE ratings SET losses=losses+1, matches=matches+1 WHERE model=?",
                (model_a,),
            )
            cur_b = cx.execute(
                "UPDATE ratings SET wins=wins+1, matches=matches+1 WHERE model=?",
                (model_b,),
            )
        else:
            cur_a = cx.execute(
                "UPDATE ratings SET draws=draws+1, matches=matches+1 WHERE model=?",
                (model_a,),
            )
            cur_b = cx.execute(
                "UPDATE ratings SET draws=draws+1, matches=matches+1 WHERE model=?",
                (model_b,),
            )
        if cur_a.rowcount == 0:
            log.warning(f"apply_match_stats: no ratings row for {model_a!r}; stats bump lost")
        if cur_b.rowcount == 0:
            log.warning(f"apply_match_stats: no ratings row for {model_b!r}; stats bump lost")

    def _elo_trends(self, cx, n: int = 5) -> dict[str, float]:
        """Return net ELO delta over the last `n` matches per model."""
        try:
            rows = cx.execute("""
                SELECT model, delta FROM (
                    SELECT model_a AS model,
                           (elo_a_after - elo_a_before) AS delta,
                           ts
                    FROM match_log
                    UNION ALL
                    SELECT model_b AS model,
                           (elo_b_after - elo_b_before) AS delta,
                           ts
                    FROM match_log
                ) ORDER BY ts DESC
            """).fetchall()
            # bucket into per-model last-N lists
            from collections import defaultdict
            buckets: dict[str, list[float]] = defaultdict(list)
            for model, delta in rows:
                if len(buckets[model]) < n:
                    buckets[model].append(delta)
            return {m: sum(deltas) for m, deltas in buckets.items()}
        except Exception:
            return {}

    @staticmethod
    def _elo_confidence(n_games: int) -> float:
        """±σ confidence interval that shrinks as match count grows.

        At n=0: ±200 (prior uncertainty matches the 1200 starting point
        being ±1 standard deviation of the FIDE provisional range).
        Converges toward ±15 for veteran models (>300 games).
        Formula: σ = 200 / sqrt(1 + n/5)
        """
        import math
        return round(200.0 / math.sqrt(1 + n_games / 5), 1)

    def leaderboard(self) -> list[dict]:
        try:
            with read_conn(self.db) as cx:
                rows = cx.execute("""
                    SELECT model, elo, wins, losses, draws, matches
                    FROM ratings ORDER BY elo DESC
                """).fetchall()
                trends = self._elo_trends(cx)
            result = []
            for i, (model, elo, wins, losses, draws, matches) in enumerate(rows):
                wr = wins / max(matches, 1)
                delta = trends.get(model, 0.0)
                trend = "up" if delta > 1.0 else ("down" if delta < -1.0 else "stable")
                ci = self._elo_confidence(matches)
                result.append({
                    "rank": i + 1, "model": model, "elo": round(elo, 1),
                    "elo_ci": ci,
                    "wins": wins, "losses": losses, "draws": draws,
                    "matches": matches, "win_rate": round(wr, 3),
                    "trend": trend, "trend_delta": round(delta, 1),
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

    def get_category_elo(self, model: str, category: str) -> float:
        try:
            with read_conn(self.db) as cx:
                row = cx.execute(
                    "SELECT elo FROM category_ratings WHERE model=? AND category=?",
                    (model, category),
                ).fetchone()
                return row[0] if row else _DEFAULT_ELO
        except Exception:
            return _DEFAULT_ELO

    def upsert_category_rating(
        self,
        model_a: str, model_b: str, category: str,
        new_elo_a: float, new_elo_b: float,
        score_a: float, score_b: float,
        now: float,
        conn=None,
    ) -> None:
        """`conn`: optional shared connection (see upsert_rating docstring)."""
        if conn is not None:
            self._upsert_category_rating_on(
                conn, model_a, model_b, category,
                new_elo_a, new_elo_b, score_a, score_b, now,
            )
            return
        with write_conn(self.db) as cx:
            self._upsert_category_rating_on(
                cx, model_a, model_b, category,
                new_elo_a, new_elo_b, score_a, score_b, now,
            )

    def _upsert_category_rating_on(
        self, cx, model_a, model_b, category,
        new_elo_a, new_elo_b, score_a, score_b, now,
    ) -> None:
        for model, elo, sa, sb in (
            (model_a, new_elo_a, score_a, score_b),
            (model_b, new_elo_b, score_b, score_a),
        ):
            if sa > sb:
                w, lo, d = 1, 0, 0
            elif sb > sa:
                w, lo, d = 0, 1, 0
            else:
                w, lo, d = 0, 0, 1
            cx.execute("""
                INSERT INTO category_ratings
                    (model, category, elo, wins, losses, draws, matches, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(model, category) DO UPDATE SET
                    elo=excluded.elo,
                    wins=wins+excluded.wins,
                    losses=losses+excluded.losses,
                    draws=draws+excluded.draws,
                    matches=matches+1,
                    updated_at=excluded.updated_at
            """, (model, category, elo, w, lo, d, now))

    def category_leaderboard(self, category: str) -> list[dict]:
        try:
            with read_conn(self.db) as cx:
                rows = cx.execute("""
                    SELECT model, elo, wins, losses, draws, matches
                    FROM category_ratings WHERE category=?
                    ORDER BY elo DESC
                """, (category,)).fetchall()
            result = []
            for i, (model, elo, wins, losses, draws, matches) in enumerate(rows):
                result.append({
                    "rank": i + 1, "model": model, "elo": round(elo, 1),
                    "wins": wins, "losses": losses, "draws": draws,
                    "matches": matches, "win_rate": round(wins / max(matches, 1), 3),
                })
            return result
        except Exception as e:
            log.error(f"Error fetching category leaderboard for {category}: {e}")
            return []

    def all_category_elos(self, model: str) -> list[dict]:
        """Return per-category ELO breakdown for one model."""
        try:
            with read_conn(self.db) as cx:
                rows = cx.execute("""
                    SELECT category, elo, wins, losses, draws, matches
                    FROM category_ratings WHERE model=?
                    ORDER BY matches DESC
                """, (model,)).fetchall()
            return [
                {
                    "category": r[0], "elo": round(r[1], 1),
                    "wins": r[2], "losses": r[3], "draws": r[4], "matches": r[5],
                    "win_rate": round(r[2] / max(r[5], 1), 3),
                }
                for r in rows
            ]
        except Exception as e:
            log.error(f"Error fetching category ELOs for {model}: {e}")
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
