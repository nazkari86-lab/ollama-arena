"""SimulationManager.start_run(reflect_every=...): opt-in periodic
reflection. Default (reflect_every=None) must leave BrainProfile
completely untouched -- existing recorded traces stay byte-for-byte
reproducible unless a run explicitly opts in.
"""
from unittest.mock import MagicMock

import pytest

from ollama_arena.backends.base import GenResult
from ollama_arena.simulations.agents.base import SimAgent
from ollama_arena.simulations.agents.profile import BrainProfile
from ollama_arena.simulations.core.runner import SimulationManager
from ollama_arena.simulations.core.types import Action, AgentSpec


class _RockAgentWithProfile(SimAgent):
    """Always plays rock (like test_simulations_runner.py's _RockAgent),
    but carries a real BrainProfile + a mock backend, so the reflection
    step (which looks for `agent.profile`/`agent._backend`/`agent.model`)
    has something to act on."""

    def __init__(self, agent_id, backend=None):
        self.agent_id = agent_id
        self.model = "fake-model"
        self.profile = BrainProfile(agent_id=agent_id)
        self._backend = backend or MagicMock()

    def act(self, obs):
        return Action(agent_id=self.agent_id, kind="choose", payload={"choice": "rock"}, raw_llm_output="")


@pytest.fixture
def shared_backend():
    backend = MagicMock()
    backend.generate.return_value = GenResult(text="Rock is a safe, predictable opener.", model="x")
    return backend


@pytest.fixture
def mgr(tmp_path, shared_backend):
    def _factory(agent_spec, scenario):
        return _RockAgentWithProfile(agent_spec.agent_id, backend=shared_backend)
    return SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=_factory)


def _run_id(mgr, rounds=6):
    return mgr.create_run(
        "rps", [AgentSpec(agent_id="a", model="x"), AgentSpec(agent_id="b", model="y")],
        config={"rounds": rounds},
    )


class TestReflectionDefaultOff:
    def test_no_reflect_every_leaves_profile_untouched(self, tmp_path, shared_backend):
        captured_agents = {}

        def _factory(agent_spec, scenario):
            agent = _RockAgentWithProfile(agent_spec.agent_id, backend=shared_backend)
            captured_agents[agent_spec.agent_id] = agent
            return agent

        mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=_factory)
        run_id = _run_id(mgr)
        mgr.start_run(run_id)  # reflect_every defaults to None

        assert captured_agents["a"].profile.recent_stream() == []
        assert captured_agents["a"].profile.status == {}

    def test_no_reflect_every_means_zero_extra_backend_calls(self, tmp_path, shared_backend):
        """The only backend calls in this run come from RPS scoring (none,
        since _RockAgentWithProfile.act() never calls the backend) -- a
        reflection call would be the ONLY way shared_backend.generate()
        gets invoked, so zero calls proves reflection never ran."""
        def _factory(agent_spec, scenario):
            return _RockAgentWithProfile(agent_spec.agent_id, backend=shared_backend)
        mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=_factory)
        run_id = _run_id(mgr)
        mgr.start_run(run_id)
        shared_backend.generate.assert_not_called()


class TestReflectionEnabled:
    def test_remembers_witnessed_events_each_tick(self, tmp_path, shared_backend):
        captured_agents = {}

        def _factory(agent_spec, scenario):
            agent = _RockAgentWithProfile(agent_spec.agent_id, backend=shared_backend)
            captured_agents[agent_spec.agent_id] = agent
            return agent

        mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=_factory)
        run_id = _run_id(mgr, rounds=6)
        mgr.start_run(run_id, reflect_every=3)

        assert captured_agents["a"].profile.recent_stream(), "profile stream should be populated when reflect_every is set"

    def test_stores_reflection_on_profile_status_every_n_ticks(self, tmp_path, shared_backend):
        captured_agents = {}

        def _factory(agent_spec, scenario):
            agent = _RockAgentWithProfile(agent_spec.agent_id, backend=shared_backend)
            captured_agents[agent_spec.agent_id] = agent
            return agent

        mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=_factory)
        run_id = _run_id(mgr, rounds=6)
        mgr.start_run(run_id, reflect_every=3)

        assert captured_agents["a"].profile.status.get("reflection") == "Rock is a safe, predictable opener."
        assert shared_backend.generate.call_count > 0

    def test_reflection_failure_does_not_crash_the_run(self, tmp_path):
        backend = MagicMock()
        backend.generate.side_effect = RuntimeError("backend unreachable")

        def _factory(agent_spec, scenario):
            return _RockAgentWithProfile(agent_spec.agent_id, backend=backend)

        mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=_factory)
        run_id = _run_id(mgr, rounds=6)
        result = mgr.start_run(run_id, reflect_every=3)  # must not raise
        assert result.truncated is True  # run still completes normally
