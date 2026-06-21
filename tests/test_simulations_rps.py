"""End-to-end Phase 1 checkpoint scenario: Rock-Paper-Scissors.

This scenario exists specifically to prove the core engine works without
any domain complexity -- these tests therefore double as core-engine
regression tests (turn/step modes, persistence, scoring, pause/resume), not
just RPS-specific behavior.
"""
import pytest

from ollama_arena.simulations.agents.base import SimAgent
from ollama_arena.simulations.core.runner import SimulationManager
from ollama_arena.simulations.core.types import Action, AgentSpec


class ScriptedAgent(SimAgent):
    """Plays a fixed, scripted sequence of choices -- deterministic without
    needing a real or mocked LLM backend."""
    def __init__(self, agent_id, choices):
        self.agent_id = agent_id
        self._choices = iter(choices)

    def act(self, obs):
        return Action(
            agent_id=self.agent_id, kind="choose",
            payload={"choice": next(self._choices)}, raw_llm_output="",
        )


def _scripted_factory(scripts):
    def factory(agent_spec, scenario):
        return scripts[agent_spec.agent_id]
    return factory


def test_rps_full_run_rock_beats_scissors(tmp_path):
    scripts = {
        "a": ScriptedAgent("a", ["rock"] * 5),
        "b": ScriptedAgent("b", ["scissors"] * 5),
    }
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=_scripted_factory(scripts))
    run_id = mgr.create_run(
        "rps", [AgentSpec(agent_id="a", model="x"), AgentSpec(agent_id="b", model="y")],
        config={"rounds": 3}, seed=1,
    )
    result = mgr.start_run(run_id)
    assert result.terminated is True
    assert result.truncated is False
    assert result.outcome["winner"] == "a"
    assert result.outcome["scores"] == {"a": 2, "b": 0}
    assert mgr.get_status(run_id).value == "completed"


def test_rps_all_draws_truncates_without_a_winner(tmp_path):
    scripts = {
        "a": ScriptedAgent("a", ["rock"] * 5),
        "b": ScriptedAgent("b", ["rock"] * 5),
    }
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=_scripted_factory(scripts))
    run_id = mgr.create_run(
        "rps", [AgentSpec(agent_id="a", model="x"), AgentSpec(agent_id="b", model="y")],
        config={"rounds": 3}, seed=1,
    )
    result = mgr.start_run(run_id)
    assert result.terminated is False
    assert result.truncated is True
    assert result.outcome == {}


def test_rps_persists_public_events_and_per_agent_transitions(tmp_path):
    scripts = {
        "a": ScriptedAgent("a", ["rock"] * 5),
        "b": ScriptedAgent("b", ["scissors"] * 5),
    }
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=_scripted_factory(scripts))
    run_id = mgr.create_run(
        "rps", [AgentSpec(agent_id="a", model="x"), AgentSpec(agent_id="b", model="y")],
        config={"rounds": 3}, seed=1,
    )
    mgr.start_run(run_id)

    events = mgr.store.get_events(run_id)
    assert all(e.kind == "round_result" for e in events)
    assert len(events) == 2  # majority (2 of 3) reached after 2 rounds

    transitions = mgr.store.get_transitions(run_id)
    assert len(transitions) == 4  # 2 agents x 2 ticks
    a_rewards = [t["reward"] for t in transitions if t["agent_id"] == "a"]
    assert a_rewards == [1.0, 1.0]


def test_rps_scorer_records_metrics(tmp_path):
    scripts = {
        "a": ScriptedAgent("a", ["rock"] * 5),
        "b": ScriptedAgent("b", ["scissors"] * 5),
    }
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=_scripted_factory(scripts))
    run_id = mgr.create_run(
        "rps", [AgentSpec(agent_id="a", model="x"), AgentSpec(agent_id="b", model="y")],
        config={"rounds": 3}, seed=1,
    )
    result = mgr.start_run(run_id)
    assert result.metrics == {"resolved": 1.0, "rounds_played": 2.0}
    metrics = mgr.store.get_metrics(run_id)
    assert {m["metric_name"]: m["value"] for m in metrics} == result.metrics


def test_rps_pause_then_resume_continues_from_checkpoint_not_from_scratch(tmp_path):
    """The key Phase 1 regression to guard: pausing mid-run and resuming
    must continue play from where it left off (same scores/round/event
    history restored), not silently restart at round 0."""
    scripts = {
        "a": ScriptedAgent("a", ["rock"] * 5),
        "b": ScriptedAgent("b", ["paper"] * 5),
    }
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=_scripted_factory(scripts))
    run_id = mgr.create_run(
        "rps", [AgentSpec(agent_id="a", model="x"), AgentSpec(agent_id="b", model="y")],
        config={"rounds": 5}, seed=1,
    )

    def stop_after_one(d):
        if d["tick"] >= 1:
            mgr.pause_run(run_id)

    paused_result = mgr.start_run(run_id, on_tick=stop_after_one)
    assert mgr.get_status(run_id).value == "paused"
    assert paused_result.terminated is False
    checkpoint = mgr.store.latest_checkpoint(run_id)
    assert checkpoint["tick"] == 1
    assert checkpoint["state"]["scores"] == {"a": 0, "b": 1}  # paper beats rock

    resumed_result = mgr.resume_run(run_id)
    assert mgr.get_status(run_id).value == "completed"
    assert resumed_result.terminated is True
    assert resumed_result.outcome["winner"] == "b"
    # 1 pre-pause tick + ticks to reach majority(3) post-resume
    assert resumed_result.ticks == 3
    assert len(mgr.store.get_events(run_id)) == 3
    assert len(mgr.store.get_transitions(run_id)) == 6  # 2 agents x 3 ticks


def test_create_run_with_unknown_scenario_raises_immediately(tmp_path):
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"))
    with pytest.raises(KeyError):
        mgr.create_run("does_not_exist", [], {})


def test_start_run_unknown_run_id_raises(tmp_path):
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"))
    with pytest.raises(KeyError):
        mgr.start_run("does_not_exist")
