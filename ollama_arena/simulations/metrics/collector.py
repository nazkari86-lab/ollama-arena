"""Thin metrics-recording wrapper over SimStore.sim_metrics.

Sim-specific metrics (win rate, survival rate, social-quality score, task
completion) live here -- NOT in performance.PerfTracker's perf_log table,
which is model-tps shaped, not episode-shaped. Raw per-LLM-call latency/tps
for sim agents should still go through the existing PerfTracker (see
agents.llm_agent.LLMSimAgent's optional perf_tracker argument); this
collector is only for the higher-level episode/scenario metrics computed by
a ScenarioScorer.
"""
from __future__ import annotations

from ..storage import SimStore


class MetricsCollector:
    def __init__(self, db_path: str = "sim.db"):
        self.store = SimStore(db_path)

    def record(self, run_id: str, metric_name: str, value: float, tick: int | None = None) -> None:
        self.store.record_metric(run_id, metric_name, value, tick=tick)

    def for_run(self, run_id: str) -> dict[str, float]:
        rows = self.store.get_metrics(run_id)
        return {r["metric_name"]: r["value"] for r in rows}
