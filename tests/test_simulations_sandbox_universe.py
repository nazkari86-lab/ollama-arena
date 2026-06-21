"""Sandbox universe: generic gather/give resource mechanics, config-driven
resource names, and the deliberate "never terminates, only truncates"
open-ended design."""
import pytest

from ollama_arena.simulations.agents.base import SimAgent
from ollama_arena.simulations.core.runner import SimulationManager
from ollama_arena.simulations.core.types import Action, AgentSpec


class ScriptedAgent(SimAgent):
    def __init__(self, agent_id, actions):
        self.agent_id = agent_id
        self._it = iter(actions)

    def act(self, obs):
        kind, payload = next(self._it)
        return Action(self.agent_id, kind, payload, "")


def test_gather_increments_named_resource(tmp_path):
    agent = ScriptedAgent("a", [("gather", {"resource": "wood"})] * 3)
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=lambda spec, scenario: agent)
    run_id = mgr.create_run("sandbox_universe", [AgentSpec(agent_id="a", model="x")],
                             config={"max_ticks": 3, "resources": ["wood", "food"]}, seed=1)
    result = mgr.start_run(run_id)
    assert result.outcome["total_gathered"] == 3.0


def test_give_transfers_resource_between_agents(tmp_path):
    agents = {
        "a": ScriptedAgent("a", [("gather", {"resource": "wood"})] * 3 +
                           [("give", {"target": "b", "resource": "wood", "amount": 2})]),
        "b": ScriptedAgent("b", [("gather", {"resource": "food"})] * 4),
    }
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=lambda spec, scenario: agents[spec.agent_id])
    run_id = mgr.create_run("sandbox_universe", [AgentSpec(agent_id="a", model="x"), AgentSpec(agent_id="b", model="y")],
                             config={"max_ticks": 4, "resources": ["wood", "food"]}, seed=1)
    mgr.start_run(run_id)
    gave_events = [e for e in mgr.store.get_events(run_id) if e.kind == "gave"]
    assert len(gave_events) == 1
    assert gave_events[0].payload == {"agent": "a", "target": "b", "resource": "wood", "amount": 2}


def test_give_more_than_owned_is_rejected(tmp_path):
    agents = {
        "a": ScriptedAgent("a", [("give", {"target": "b", "resource": "wood", "amount": 100})]),
        "b": ScriptedAgent("b", [("gather", {"resource": "wood"})]),
    }
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=lambda spec, scenario: agents[spec.agent_id])
    run_id = mgr.create_run("sandbox_universe", [AgentSpec(agent_id="a", model="x"), AgentSpec(agent_id="b", model="y")],
                             config={"max_ticks": 1}, seed=1)
    mgr.start_run(run_id)
    invalid = [e for e in mgr.store.get_events(run_id) if e.kind == "invalid_action"]
    assert len(invalid) == 1


def test_gather_unknown_resource_is_rejected(tmp_path):
    agent = ScriptedAgent("a", [("gather", {"resource": "diamonds"})])
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=lambda spec, scenario: agent)
    run_id = mgr.create_run("sandbox_universe", [AgentSpec(agent_id="a", model="x")],
                             config={"max_ticks": 1, "resources": ["wood"]}, seed=1)
    mgr.start_run(run_id)
    invalid = [e for e in mgr.store.get_events(run_id) if e.kind == "invalid_action"]
    assert len(invalid) == 1


def test_never_terminates_only_truncates(tmp_path):
    agent = ScriptedAgent("a", [("gather", {"resource": "wood"})] * 100)
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=lambda spec, scenario: agent)
    run_id = mgr.create_run("sandbox_universe", [AgentSpec(agent_id="a", model="x")],
                             config={"max_ticks": 5}, seed=1)
    result = mgr.start_run(run_id)
    assert result.terminated is False
    assert result.truncated is True
    assert result.ticks == 5


def test_default_resources_used_when_not_configured(tmp_path):
    from ollama_arena.simulations.scenarios.sandbox_universe import DEFAULT_RESOURCES, SandboxUniverseWorld
    world = SandboxUniverseWorld(["a"])
    world.reset()
    assert set(world.resource_names) == set(DEFAULT_RESOURCES)


def test_too_few_agents_raises_at_world_construction():
    from ollama_arena.simulations.scenarios.sandbox_universe import SandboxUniverseWorld
    with pytest.raises(ValueError, match="at least 1"):
        SandboxUniverseWorld([])
