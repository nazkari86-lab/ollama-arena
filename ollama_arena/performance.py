"""Per-generation performance log and aggregates.

These numbers include HTTP overhead and the model server's scheduling
behaviour, not just raw decode speed. Useful for relative comparisons
within one backend; treat absolute values with care.
"""
from __future__ import annotations
import sqlite3, statistics, time
from typing import Optional


class PerfTracker:
    """Tracks per-model generation metrics and MCP tool latency across runs."""

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
                    category TEXT,
                    tokens_in INTEGER,
                    tokens_out INTEGER,
                    latency_s REAL,
                    tps REAL,
                    time_to_first REAL,
                    ts REAL
                );
                CREATE INDEX IF NOT EXISTS perf_model ON perf_log(model);
                CREATE TABLE IF NOT EXISTS tool_perf_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_name TEXT,
                    model TEXT,
                    category TEXT,
                    latency_s REAL,
                    ts REAL
                );
                CREATE INDEX IF NOT EXISTS tool_perf_name ON tool_perf_log(tool_name);
            """)
            # Backfill category column on older DBs
            cols = {r[1] for r in cx.execute("PRAGMA table_info(perf_log)").fetchall()}
            if "category" not in cols:
                cx.execute("ALTER TABLE perf_log ADD COLUMN category TEXT")

    def record(self, model: str, backend: str, tokens_in: int, tokens_out: int,
               latency_s: float, tps: float, time_to_first: float,
               category: Optional[str] = None):
        with self._conn() as cx:
            cx.execute(
                "INSERT INTO perf_log(model,backend,category,tokens_in,tokens_out,"
                "latency_s,tps,time_to_first,ts) VALUES (?,?,?,?,?,?,?,?,?)",
                (model, backend, category, tokens_in, tokens_out,
                 latency_s, tps, time_to_first, time.time()),
            )

    def record_tool(self, tool_name: str, model: str, latency_s: float,
                    category: Optional[str] = None):
        """Log MCP tool execution latency for agent-trace analytics."""
        with self._conn() as cx:
            cx.execute(
                "INSERT INTO tool_perf_log(tool_name,model,category,latency_s,ts) "
                "VALUES (?,?,?,?,?)",
                (tool_name, model, category, latency_s, time.time()),
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
                "tools": self._tool_stats_for_model(model),
            })
        return sorted(out, key=lambda x: -x["tps_mean"])

    def tool_stats(self) -> list[dict]:
        """Aggregate per-tool latency across all models."""
        with self._conn() as cx:
            rows = cx.execute("""
                SELECT tool_name, COUNT(*), AVG(latency_s),
                       MIN(latency_s), MAX(latency_s)
                FROM tool_perf_log GROUP BY tool_name
            """).fetchall()
        return [
            {
                "tool": name,
                "n_calls": n,
                "latency_mean_s": round(avg or 0, 3),
                "latency_min_s": round(mn or 0, 3),
                "latency_max_s": round(mx or 0, 3),
            }
            for name, n, avg, mn, mx in rows
        ]

    def category_stats(self) -> list[dict]:
        """Aggregate TTFT/TPS by task category."""
        with self._conn() as cx:
            rows = cx.execute("""
                SELECT COALESCE(category, 'unknown'), COUNT(*),
                       AVG(tps), AVG(latency_s), AVG(time_to_first)
                FROM perf_log GROUP BY category
            """).fetchall()
        return [
            {
                "category": cat,
                "n_samples": n,
                "tps_mean": round(tps or 0, 1),
                "latency_mean_s": round(lat or 0, 2),
                "ttft_mean_s": round(ttft or 0, 2),
            }
            for cat, n, tps, lat, ttft in rows
        ]

    def _tool_stats_for_model(self, model: str) -> list[dict]:
        with self._conn() as cx:
            rows = cx.execute("""
                SELECT tool_name, COUNT(*), AVG(latency_s)
                FROM tool_perf_log WHERE model=? GROUP BY tool_name
            """, (model,)).fetchall()
        return [
            {"tool": name, "n_calls": n, "latency_mean_s": round(avg or 0, 3)}
            for name, n, avg in rows
        ]

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

    def export_summary(self) -> dict:
        """Combined payload for /api/perf and visualize charts."""
        return {
            "models": self.stats(),
            "tools": self.tool_stats(),
            "categories": self.category_stats(),
        }
