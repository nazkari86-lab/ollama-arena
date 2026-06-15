"""Per-generation performance log and aggregates.

These numbers include HTTP overhead and the model server's scheduling
behaviour, not just raw decode speed. Useful for relative comparisons
within one backend; treat absolute values with care.
"""
from __future__ import annotations
import sqlite3, statistics, time
from typing import Optional


class PerfTracker:
    """Tracks per-model generation metrics across the arena run."""

    def __init__(self, db_path: str = "arena.db"):
        self.db = db_path
        self._init()

    def _conn(self):
        return sqlite3.connect(self.db)

    def _init(self):
        with self._conn() as cx:
            cx.executescript("""
                CREATE TABLE IF NOT EXISTS perf_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model TEXT,
                    backend TEXT,
                    tokens_in INTEGER,
                    tokens_out INTEGER,
                    latency_s REAL,
                    tps REAL,
                    time_to_first REAL,
                    ts REAL
                );
                CREATE INDEX IF NOT EXISTS perf_model ON perf_log(model);
            """)

    def record(self, model: str, backend: str, tokens_in: int, tokens_out: int,
               latency_s: float, tps: float, time_to_first: float):
        with self._conn() as cx:
            cx.execute(
                "INSERT INTO perf_log(model,backend,tokens_in,tokens_out,"
                "latency_s,tps,time_to_first,ts) VALUES (?,?,?,?,?,?,?,?)",
                (model, backend, tokens_in, tokens_out,
                 latency_s, tps, time_to_first, time.time()),
            )

    def stats(self) -> list[dict]:
        with self._conn() as cx:
            rows = cx.execute("""
                SELECT model, COUNT(*),
                       AVG(tokens_out), AVG(latency_s), AVG(tps), AVG(time_to_first)
                FROM perf_log GROUP BY model
            """).fetchall()
        out = []
        for model, n, tok_avg, lat_avg, tps_avg, ttft_avg in rows:
            samples = self._samples(model)
            tps_p95 = self._pct(samples["tps"], 0.95)
            lat_p95 = self._pct(samples["latency"], 0.95)
            out.append({
                "model": model,
                "n_samples": n,
                "avg_tokens_out": round(tok_avg or 0, 1),
                "latency_mean_s": round(lat_avg or 0, 2),
                "latency_p95_s":  round(lat_p95, 2),
                "tps_mean":       round(tps_avg or 0, 1),
                "tps_p95":        round(tps_p95, 1),
                "ttft_mean_s":    round(ttft_avg or 0, 2),
            })
        return sorted(out, key=lambda x: -x["tps_mean"])

    def _samples(self, model: str) -> dict[str, list[float]]:
        with self._conn() as cx:
            rows = cx.execute(
                "SELECT tps, latency_s FROM perf_log WHERE model=?", (model,)
            ).fetchall()
        return {"tps": [r[0] for r in rows], "latency": [r[1] for r in rows]}

    @staticmethod
    def _pct(values: list[float], p: float) -> float:
        if not values:
            return 0.0
        s = sorted(values)
        k = int(len(s) * p)
        return s[min(k, len(s) - 1)]
