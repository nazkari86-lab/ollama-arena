"""eval.compare.compare_runs() -- powers both `sim benchmark` CLI output
and the dashboard's comparison charts from one implementation."""
import pytest

from ollama_arena.simulations.eval.compare import compare_runs
from ollama_arena.simulations.storage import SimStore


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "sim.db")


def test_compare_runs_collects_metrics_per_run(db_path):
    store = SimStore(db_path)
    r1 = store.create_run("rps", [], {})
    r2 = store.create_run("rps", [], {})
    store.record_metric(r1, "resolved", 1.0)
    store.record_metric(r1, "rounds_played", 2.0)
    store.record_metric(r2, "resolved", 0.0)
    store.record_metric(r2, "rounds_played", 3.0)

    report = compare_runs([r1, r2], db_path=db_path)
    assert report.scenario == "rps"
    assert report.metrics_by_run[r1]["resolved"] == 1.0
    assert report.metrics_by_run[r2]["rounds_played"] == 3.0
    assert report.metric_names == ["resolved", "rounds_played"]


def test_compare_runs_scenario_is_none_when_mixed(db_path):
    store = SimStore(db_path)
    r1 = store.create_run("rps", [], {})
    r2 = store.create_run("mafia", [], {})
    report = compare_runs([r1, r2], db_path=db_path)
    assert report.scenario is None


def test_compare_runs_skips_unknown_run_ids(db_path):
    store = SimStore(db_path)
    r1 = store.create_run("rps", [], {})
    report = compare_runs([r1, "does_not_exist"], db_path=db_path)
    assert report.run_ids == [r1]


def test_best_run_picks_highest_by_default(db_path):
    store = SimStore(db_path)
    r1 = store.create_run("rps", [], {})
    r2 = store.create_run("rps", [], {})
    store.record_metric(r1, "score", 0.4)
    store.record_metric(r2, "score", 0.9)
    report = compare_runs([r1, r2], db_path=db_path)
    assert report.best_run("score") == r2


def test_best_run_lower_is_better(db_path):
    store = SimStore(db_path)
    r1 = store.create_run("rps", [], {})
    r2 = store.create_run("rps", [], {})
    store.record_metric(r1, "latency", 0.4)
    store.record_metric(r2, "latency", 0.9)
    report = compare_runs([r1, r2], db_path=db_path)
    assert report.best_run("latency", higher_is_better=False) == r1


def test_best_run_unknown_metric_returns_none(db_path):
    store = SimStore(db_path)
    r1 = store.create_run("rps", [], {})
    report = compare_runs([r1], db_path=db_path)
    assert report.best_run("nope") is None
