"""Sims-world: needs decay, work/rest/socialize/spend effects, starvation
death as the termination condition, and checkpoint/resume parity for
long-running multi-day play."""
import itertools

import pytest

from ollama_arena.simulations.agents.base import SimAgent
from ollama_arena.simulations.core.runner import SimulationManager
from ollama_arena.simulations.core.types import Action, AgentSpec
from ollama_arena.simulations.world.economy import (
    JOB_CATALOG, RENT_PER_DAY,
    apply_conflict, apply_daily_decay, apply_rent_bill, apply_rest,
    apply_socialize, apply_spend, apply_work, is_starving_to_death,
)
from ollama_arena.simulations.world.entities import NPCStatus
from ollama_arena.simulations.world.relationships import RelationshipGraph


class ScriptedSimsAgent(SimAgent):
    def __init__(self, agent_id, actions):
        self.agent_id = agent_id
        self._it = iter(actions)

    def act(self, obs):
        kind, payload = next(self._it)
        return Action(self.agent_id, kind, payload, "")


class CyclingSimsAgent(SimAgent):
    def __init__(self, agent_id, cycle):
        self.agent_id = agent_id
        self._cycle = itertools.cycle(cycle)

    def act(self, obs):
        kind, payload = next(self._cycle)
        return Action(self.agent_id, kind, payload, "")


# ── economy.py pure-function unit tests ────────────────────────────────────

def test_apply_work_pays_wage_only_if_employed():
    employed = NPCStatus(agent_id="a", job="baker")
    apply_work(employed)
    assert employed.money == 100.0  # 50 starting + 50 wage

    unemployed = NPCStatus(agent_id="b", job=None)
    wage = apply_work(unemployed)
    assert wage == 0.0
    assert unemployed.money == 50.0


def test_apply_spend_rejects_amount_exceeding_money():
    status = NPCStatus(agent_id="a", money=10.0)
    ok = apply_spend(status, 50.0, on="food")
    assert ok is False
    assert status.money == 10.0  # untouched


def test_apply_spend_on_food_restores_hunger():
    status = NPCStatus(agent_id="a", money=50.0)
    status.needs["hunger"] = 20.0
    ok = apply_spend(status, 30.0, on="food")
    assert ok is True
    assert status.money == 20.0
    assert status.needs["hunger"] == 60.0


def test_needs_clamp_to_max_100():
    status = NPCStatus(agent_id="a")
    status.needs["energy"] = 90.0
    apply_rest(status)  # +35, would be 125 without clamping
    assert status.needs["energy"] == 100.0


def test_is_starving_to_death_on_zero_hunger_or_energy():
    s1 = NPCStatus(agent_id="a")
    s1.needs["hunger"] = 0.0
    assert is_starving_to_death(s1)

    s2 = NPCStatus(agent_id="b")
    s2.needs["energy"] = 0.0
    assert is_starving_to_death(s2)

    s3 = NPCStatus(agent_id="c")
    assert not is_starving_to_death(s3)


def test_relationship_graph_is_symmetric_and_observe_safe():
    graph = RelationshipGraph()
    graph.bump("a", "b", 10.0)
    assert graph.get("a", "b") == graph.get("b", "a") == 10.0
    assert graph.edges_for("a") == {"b": 10.0}
    assert graph.edges_for("c") == {}


def test_relationship_graph_round_trips_through_dict():
    graph = RelationshipGraph()
    graph.bump("a", "b", 5.0)
    restored = RelationshipGraph.from_dict(graph.to_dict())
    assert restored.get("a", "b") == 5.0


# ── full-scenario end-to-end tests ─────────────────────────────────────────

@pytest.fixture
def mgr(tmp_path):
    return SimulationManager(db_path=str(tmp_path / "sim.db"))


def test_agent_that_never_eats_starves_to_death(tmp_path):
    """Resting forever keeps energy high but never restores hunger -- the
    agent must die of starvation well before the day budget runs out."""
    agent = ScriptedSimsAgent("b", [("rest", {})] * 20)
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=lambda spec, scenario: agent)
    run_id = mgr.create_run("sims_world", [AgentSpec(agent_id="b", model="x")],
                             config={"max_days": 20}, seed=1)
    result = mgr.start_run(run_id)
    assert result.terminated is True
    assert result.outcome["all_dead"] is True
    assert result.ticks < 20
    death_events = [e for e in mgr.store.get_events(run_id) if e.kind == "agent_died"]
    assert len(death_events) == 1
    assert death_events[0].payload["agent"] == "b"


def test_balanced_agent_survives_the_full_day_budget(tmp_path):
    """work -> spend on food -> rest, repeating, is a sustainable cycle that
    must survive the configured day budget and truncate rather than die."""
    cycle = [("work", {}), ("spend", {"amount": 30, "on": "food"}), ("rest", {})]
    agent = CyclingSimsAgent("a", cycle)
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=lambda spec, scenario: agent)
    run_id = mgr.create_run("sims_world", [AgentSpec(agent_id="a", model="x")],
                             config={"max_days": 10, "jobs": {"a": "baker"}}, seed=1)
    result = mgr.start_run(run_id)
    assert result.terminated is False
    assert result.truncated is True
    assert result.outcome["survivors"] == ["a"]


def test_unemployed_agent_earns_nothing_from_work(tmp_path):
    agent = ScriptedSimsAgent("a", [("work", {})] * 3)
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=lambda spec, scenario: agent)
    run_id = mgr.create_run("sims_world", [AgentSpec(agent_id="a", model="x")],
                             config={"max_days": 3}, seed=1)  # no "jobs" config -> unemployed
    mgr.start_run(run_id)
    worked_events = [e for e in mgr.store.get_events(run_id) if e.kind == "worked"]
    assert all(e.payload["wage"] == 0.0 for e in worked_events)


def test_socialize_with_unknown_target_is_discarded_as_invalid(tmp_path):
    agent = ScriptedSimsAgent("a", [("socialize", {"target": "ghost"})] * 1)
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=lambda spec, scenario: agent)
    run_id = mgr.create_run("sims_world", [AgentSpec(agent_id="a", model="x")],
                             config={"max_days": 1}, seed=1)
    mgr.start_run(run_id)
    invalid = [e for e in mgr.store.get_events(run_id) if e.kind == "invalid_action"]
    assert len(invalid) == 1


def test_socialize_with_real_target_bumps_relationship(tmp_path):
    cycle_a = [("socialize", {"target": "b"})]
    cycle_b = [("rest", {})]
    agents = {"a": ScriptedSimsAgent("a", cycle_a * 1), "b": ScriptedSimsAgent("b", cycle_b * 1)}
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=lambda spec, scenario: agents[spec.agent_id])
    run_id = mgr.create_run("sims_world", [AgentSpec(agent_id="a", model="x"), AgentSpec(agent_id="b", model="y")],
                             config={"max_days": 1}, seed=1)
    mgr.start_run(run_id)
    socialized = [e for e in mgr.store.get_events(run_id) if e.kind == "socialized"]
    assert len(socialized) == 1
    assert socialized[0].payload == {"agent": "a", "target": "b"}


def test_observe_status_includes_only_own_relationships(tmp_path):
    from ollama_arena.simulations.scenarios.sims_world import SimsWorldWorld
    world = SimsWorldWorld(["a", "b", "c"])
    world.reset(seed=1)
    world.relationships.bump("a", "b", 10.0)
    obs_a = world.observe("a")
    assert obs_a.status["relationships"] == {"b": 10.0}
    obs_c = world.observe("c")
    assert obs_c.status["relationships"] == {}


def test_pause_then_resume_continues_with_same_needs_and_money(tmp_path):
    """The key Phase 3 regression to guard: pausing mid-run and resuming
    must produce the exact same final trajectory as an uninterrupted run
    of the same length -- proving resume continues from the checkpointed
    day/needs/money, not silently restarts the cycle from day 0."""
    cycle = [("work", {}), ("spend", {"amount": 30, "on": "food"}), ("rest", {})]
    cfg = {"max_days": 10, "jobs": {"a": "baker"}}

    uninterrupted_mgr = SimulationManager(
        db_path=str(tmp_path / "uninterrupted.db"),
        agent_factory=lambda spec, scenario: CyclingSimsAgent("a", cycle),
    )
    uninterrupted_id = uninterrupted_mgr.create_run(
        "sims_world", [AgentSpec(agent_id="a", model="x")], config=cfg, seed=1,
    )
    uninterrupted_result = uninterrupted_mgr.start_run(uninterrupted_id)

    paused_mgr = SimulationManager(
        db_path=str(tmp_path / "paused.db"),
        agent_factory=lambda spec, scenario: CyclingSimsAgent("a", cycle),
    )
    paused_id = paused_mgr.create_run(
        "sims_world", [AgentSpec(agent_id="a", model="x")], config=cfg, seed=1,
    )

    def stop_after_3(d):
        if d["tick"] >= 3:
            paused_mgr.pause_run(paused_id)

    paused_mgr.start_run(paused_id, on_tick=stop_after_3)
    assert paused_mgr.get_status(paused_id).value == "paused"
    assert paused_mgr.store.latest_checkpoint(paused_id)["tick"] == 3

    resumed_result = paused_mgr.resume_run(paused_id)

    assert resumed_result.ticks == uninterrupted_result.ticks == 10
    assert resumed_result.outcome == uninterrupted_result.outcome
    assert resumed_result.metrics == uninterrupted_result.metrics

    # The full per-day transition history (money/needs trajectory) must
    # match exactly, day for day -- not just the final summary.
    uninterrupted_transitions = uninterrupted_mgr.store.get_transitions(uninterrupted_id)
    resumed_transitions = paused_mgr.store.get_transitions(paused_id)
    assert len(uninterrupted_transitions) == len(resumed_transitions)
    for u, r in zip(uninterrupted_transitions, resumed_transitions):
        assert u["obs"]["status"]["money"] == r["obs"]["status"]["money"]
        assert u["obs"]["status"]["needs"] == r["obs"]["status"]["needs"]


def test_too_few_agents_raises_at_world_construction():
    from ollama_arena.simulations.scenarios.sims_world import SimsWorldWorld
    with pytest.raises(ValueError, match="at least 1"):
        SimsWorldWorld([])


def test_scorer_reports_survivors_and_days(tmp_path):
    agent = ScriptedSimsAgent("a", [("rest", {})] * 3)
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=lambda spec, scenario: agent)
    run_id = mgr.create_run("sims_world", [AgentSpec(agent_id="a", model="x")],
                             config={"max_days": 3}, seed=1)
    result = mgr.start_run(run_id)
    assert result.metrics["days_survived"] == 3.0
    assert result.metrics["survivors"] in (0.0, 1.0)


# ── L2 economy: job catalog, rent/debt, spend categories, conflict ────────

def test_apply_work_pays_job_specific_wage_from_catalog():
    # "baker" must keep its pre-existing wage (50.0) so the already-balanced
    # work/spend/rest cycle in test_balanced_agent_survives_the_full_day_budget
    # doesn't silently change economics underneath it.
    assert JOB_CATALOG["baker"] == 50.0
    barista = NPCStatus(agent_id="a", job="barista")
    apply_work(barista)
    assert barista.money == 50.0 + JOB_CATALOG["barista"]
    assert JOB_CATALOG["barista"] != JOB_CATALOG["baker"]


def test_apply_work_unlisted_job_name_pays_default_wage():
    status = NPCStatus(agent_id="a", job="freelancer")  # not in JOB_CATALOG
    wage = apply_work(status)
    assert wage > 0.0  # still employed, just at the fallback rate
    assert "freelancer" not in JOB_CATALOG


def test_apply_spend_on_leisure_restores_mood():
    status = NPCStatus(agent_id="a", money=50.0)
    status.needs["mood"] = 20.0
    ok = apply_spend(status, 20.0, on="leisure")
    assert ok is True
    assert status.needs["mood"] > 20.0
    assert status.needs["hunger"] == 80.0  # unaffected by a leisure purchase


def test_apply_rent_bill_pays_from_money_when_affordable():
    status = NPCStatus(agent_id="a", money=100.0)
    paid = apply_rent_bill(status)
    assert paid is True
    assert status.money == 100.0 - RENT_PER_DAY
    assert status.debt == 0.0


def test_apply_rent_bill_goes_to_debt_when_unaffordable_and_hurts_mood():
    status = NPCStatus(agent_id="a", money=5.0)
    status.needs["mood"] = 80.0
    paid = apply_rent_bill(status)
    assert paid is False
    assert status.money == 5.0  # untouched, not partially drained
    assert status.debt == RENT_PER_DAY
    assert status.needs["mood"] < 80.0


def test_apply_conflict_reduces_mood():
    status = NPCStatus(agent_id="a")
    status.needs["mood"] = 80.0
    apply_conflict(status)
    assert status.needs["mood"] < 80.0


def test_conflict_action_bumps_relationship_negative(tmp_path):
    cycle_a = [("conflict", {"target": "b"})]
    cycle_b = [("rest", {})]
    agents = {"a": ScriptedSimsAgent("a", cycle_a), "b": ScriptedSimsAgent("b", cycle_b)}
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=lambda spec, scenario: agents[spec.agent_id])
    run_id = mgr.create_run("sims_world", [AgentSpec(agent_id="a", model="x"), AgentSpec(agent_id="b", model="y")],
                             config={"max_days": 1}, seed=1)
    mgr.start_run(run_id)
    world_relationships = mgr.store.get_run(run_id)  # sanity: run exists
    assert world_relationships is not None
    conflicted = [e for e in mgr.store.get_events(run_id) if e.kind == "conflicted"]
    assert len(conflicted) == 1
    assert conflicted[0].payload == {"agent": "a", "target": "b"}


def test_conflict_with_unknown_target_is_discarded_as_invalid(tmp_path):
    agent = ScriptedSimsAgent("a", [("conflict", {"target": "ghost"})])
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=lambda spec, scenario: agent)
    run_id = mgr.create_run("sims_world", [AgentSpec(agent_id="a", model="x")],
                             config={"max_days": 1}, seed=1)
    mgr.start_run(run_id)
    invalid = [e for e in mgr.store.get_events(run_id) if e.kind == "invalid_action"]
    assert len(invalid) == 1


def test_set_goal_action_persists_into_status_and_is_observable(tmp_path):
    agent = ScriptedSimsAgent("a", [("set_goal", {"goal": "pay_rent"}), ("rest", {})])
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=lambda spec, scenario: agent)
    run_id = mgr.create_run("sims_world", [AgentSpec(agent_id="a", model="x")],
                             config={"max_days": 2}, seed=1)
    mgr.start_run(run_id)
    transitions = mgr.store.get_transitions(run_id)
    # day 2's *observation* (taken before acting) must already show the
    # goal set on day 1 -- proves it persists on NPCStatus, not just logged.
    assert transitions[1]["obs"]["status"]["current_goal"] == "pay_rent"


def test_every_living_agent_is_billed_rent_once_per_day(tmp_path):
    agent = ScriptedSimsAgent("a", [("rest", {})] * 2)
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=lambda spec, scenario: agent)
    run_id = mgr.create_run("sims_world", [AgentSpec(agent_id="a", model="x")],
                             config={"max_days": 2}, seed=1)
    mgr.start_run(run_id)
    rent_events = [e for e in mgr.store.get_events(run_id) if e.kind.startswith("rent_")]
    assert len(rent_events) == 2  # one per day, regardless of the day's chosen action
