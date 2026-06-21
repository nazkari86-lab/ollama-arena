"""Compare multiple sim runs -- powers both `sim benchmark`'s CLI output and
the dashboard's comparison charts from one implementation."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..storage import SimStore


@dataclass
class ComparisonReport:
    run_ids: list[str]
    scenario: str | None
    metrics_by_run: dict[str, dict[str, float]] = field(default_factory=dict)
    metric_names: list[str] = field(default_factory=list)

    def best_run(self, metric_name: str, higher_is_better: bool = True) -> str | None:
        candidates = [
            (run_id, m[metric_name]) for run_id, m in self.metrics_by_run.items()
            if metric_name in m
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda kv: kv[1] if higher_is_better else -kv[1])[0]


def compare_runs(run_ids: list[str], db_path: str = "sim.db") -> ComparisonReport:
    store = SimStore(db_path)
    metrics_by_run: dict[str, dict[str, float]] = {}
    scenarios: set[str] = set()
    for run_id in run_ids:
        run = store.get_run(run_id)
        if run is None:
            continue
        scenarios.add(run["scenario"])
        metrics_by_run[run_id] = {
            m["metric_name"]: m["value"] for m in store.get_metrics(run_id)
        }
    names = sorted({name for m in metrics_by_run.values() for name in m})
    return ComparisonReport(
        run_ids=list(metrics_by_run),
        scenario=next(iter(scenarios)) if len(scenarios) == 1 else None,
        metrics_by_run=metrics_by_run,
        metric_names=names,
    )
