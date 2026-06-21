"""sim.db persistence: runs/events/transitions/checkpoints/metrics."""
import pytest

from ollama_arena.simulations.core.types import (
    Action, AgentSpec, Event, Observation, Transition, WITNESS_ALL,
)
from ollama_arena.simulations.storage import SimStore


@pytest.fixture
def store(tmp_path):
    return SimStore(db_path=str(tmp_path / "sim.db"))


def test_create_and_get_run_round_trips(store):
    run_id = store.create_run(
        "rps", [AgentSpec(agent_id="a", model="llama3.2:3b")],
        config={"rounds": 3}, seed=42,
    )
    run = store.get_run(run_id)
    assert run["scenario"] == "rps"
    assert run["status"] == "not_started"
    assert run["seed"] == 42
    assert run["agents"] == [{"agent_id": "a", "model": "llama3.2:3b", "config": {}}]
    assert run["config"] == {"rounds": 3}


def test_get_run_unknown_id_returns_none(store):
    assert store.get_run("does_not_exist") is None


def test_update_run_status_sets_status_and_timestamp(store):
    run_id = store.create_run("rps", [], {})
    store.update_run_status(run_id, "in_progress", started_at=123.0)
    run = store.get_run(run_id)
    assert run["status"] == "in_progress"
    assert run["started_at"] == 123.0


def test_update_run_status_without_timestamps(store):
    """Regression guard: the SQL-building branch for 'status only, no
    timestamp columns' must produce valid SQL with correctly-ordered
    params -- this path is exercised by pause_run()."""
    run_id = store.create_run("rps", [], {})
    store.update_run_status(run_id, "paused")
    assert store.get_run(run_id)["status"] == "paused"


def test_set_run_outcome(store):
    run_id = store.create_run("rps", [], {})
    store.set_run_outcome(run_id, {"winner": "a"})
    assert store.get_run(run_id)["outcome"] == {"winner": "a"}


def test_list_runs_filters_by_scenario_and_orders_newest_first(store):
    r1 = store.create_run("rps", [], {})
    r2 = store.create_run("mafia", [], {})
    r3 = store.create_run("rps", [], {})
    rps_runs = [r["run_id"] for r in store.list_runs(scenario="rps")]
    assert rps_runs == [r3, r1]
    assert len(store.list_runs()) == 3


def test_append_and_get_events_preserves_witness_ids(store):
    run_id = store.create_run("rps", [], {})
    private = Event(id="e1", tick=0, kind="night_kill", payload={"target": "b"},
                     witness_ids=frozenset({"mafia_1"}))
    public = Event(id="e2", tick=0, kind="announce", payload={},
                    witness_ids=WITNESS_ALL)
    store.append_events(run_id, [private, public])
    events = store.get_events(run_id)
    assert len(events) == 2
    assert events[0].witness_ids == frozenset({"mafia_1"})
    assert events[1].witness_ids == WITNESS_ALL


def test_get_events_filtered_by_witness_excludes_unwitnessed(store):
    run_id = store.create_run("mafia", [], {})
    private = Event(id="e1", tick=0, kind="night_kill", payload={},
                     witness_ids=frozenset({"mafia_1"}))
    store.append_events(run_id, [private])
    assert store.get_events(run_id, witness_id="mafia_1") == [private]
    assert store.get_events(run_id, witness_id="villager_1") == []


def test_append_events_empty_list_is_a_noop(store):
    run_id = store.create_run("rps", [], {})
    store.append_events(run_id, [])
    assert store.get_events(run_id) == []


def test_append_and_get_transitions_round_trips(store):
    run_id = store.create_run("rps", [], {})
    obs = Observation(agent_id="a", tick=0, visible_events=())
    action = Action(agent_id="a", kind="choose", payload={"choice": "rock"}, raw_llm_output="{}")
    transition = Transition(
        tick=1, agent_id="a", obs=obs, action=action, reward=1.0,
        terminated=False, truncated=False, info={"x": 1},
    )
    store.append_transitions(run_id, [transition])
    rows = store.get_transitions(run_id)
    assert len(rows) == 1
    assert rows[0]["agent_id"] == "a"
    assert rows[0]["action"]["payload"] == {"choice": "rock"}
    assert rows[0]["terminated"] is False
    assert rows[0]["info"] == {"x": 1}


def test_checkpoint_round_trip_and_latest(store):
    run_id = store.create_run("rps", [], {})
    cp1 = store.save_checkpoint(run_id, tick=1, state={"round": 1})
    cp2 = store.save_checkpoint(run_id, tick=2, state={"round": 2})
    assert store.get_checkpoint(cp1)["state"] == {"round": 1}
    latest = store.latest_checkpoint(run_id)
    assert latest["checkpoint_id"] == cp2
    assert latest["tick"] == 2


def test_latest_checkpoint_none_when_no_checkpoints_saved(store):
    run_id = store.create_run("rps", [], {})
    assert store.latest_checkpoint(run_id) is None


def test_record_and_get_metrics(store):
    run_id = store.create_run("rps", [], {})
    store.record_metric(run_id, "resolved", 1.0, tick=3)
    store.record_metric(run_id, "rounds_played", 3.0, tick=3)
    metrics = store.get_metrics(run_id)
    assert {m["metric_name"]: m["value"] for m in metrics} == {
        "resolved": 1.0, "rounds_played": 3.0,
    }


def test_in_memory_db_shares_one_connection_across_calls():
    """:memory: must behave as one logical database across the lifetime of
    a SimStore instance, not a fresh empty DB per connection (sqlite3's
    default :memory: behavior, which genome/db.py's GenomeStore already
    works around the same way)."""
    store = SimStore(db_path=":memory:")
    run_id = store.create_run("rps", [], {})
    assert store.get_run(run_id) is not None
