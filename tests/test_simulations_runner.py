"""SimulationManager lifecycle: create/start/pause/resume/list/status.

Modeled on the verbs of tasks.long_horizon.LongHorizonTaskManager, but each
test here exercises the sim.db-backed implementation specifically.
"""
import pytest

from ollama_arena.simulations.agents.base import SimAgent
from ollama_arena.simulations.core.runner import SimStatus, SimulationManager
from ollama_arena.simulations.core.scenario import get_scenario
from ollama_arena.simulations.core.types import Action, AgentSpec


class _RockAgent(SimAgent):
    def __init__(self, agent_id):
        self.agent_id = agent_id

    def act(self, obs):
        return Action(agent_id=self.agent_id, kind="choose", payload={"choice": "rock"}, raw_llm_output="")


def _factory(agent_spec, scenario):
    return _RockAgent(agent_spec.agent_id)


@pytest.fixture
def mgr(tmp_path):
    return SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=_factory)


def test_create_run_returns_id_in_not_started_status(mgr):
    run_id = mgr.create_run(
        "rps", [AgentSpec(agent_id="a", model="x"), AgentSpec(agent_id="b", model="y")],
        config={"rounds": 3},
    )
    assert mgr.get_status(run_id) == SimStatus.NOT_STARTED


def test_get_status_unknown_run_raises(mgr):
    with pytest.raises(KeyError):
        mgr.get_status("nope")


def test_list_runs_returns_created_run(mgr):
    run_id = mgr.create_run(
        "rps", [AgentSpec(agent_id="a", model="x"), AgentSpec(agent_id="b", model="y")], {},
    )
    runs = mgr.list_runs()
    assert any(r["run_id"] == run_id for r in runs)


def test_list_runs_filters_by_scenario(mgr):
    rps_id = mgr.create_run(
        "rps", [AgentSpec(agent_id="a", model="x"), AgentSpec(agent_id="b", model="y")], {},
    )
    filtered = mgr.list_runs(scenario_name="rps")
    assert all(r["scenario"] == "rps" for r in filtered)
    assert any(r["run_id"] == rps_id for r in filtered)


def test_start_run_with_draw_only_agents_truncates_and_completes(mgr):
    """Both agents always play rock -> every round is a draw -> the run
    truncates (no winner) but the manager still marks it 'completed', not
    'failed' -- truncation is a normal episode outcome, not an error."""
    run_id = mgr.create_run(
        "rps", [AgentSpec(agent_id="a", model="x"), AgentSpec(agent_id="b", model="y")],
        config={"rounds": 3},
    )
    result = mgr.start_run(run_id)
    assert result.truncated is True
    assert mgr.get_status(run_id) == SimStatus.COMPLETED


def test_tick_callback_exposes_model_actions_and_visible_state(mgr):
    run_id = mgr.create_run(
        "rps", [AgentSpec(agent_id="a", model="x"), AgentSpec(agent_id="b", model="y")],
        config={"rounds": 1},
    )
    ticks = []

    mgr.start_run(run_id, on_tick=ticks.append)

    assert ticks
    tick = ticks[0]
    assert tick["step_mode"] == "simultaneous"
    assert {agent["model"] for agent in tick["agents"]} == {"x", "y"}
    assert all(agent["action"] == {"kind": "choose", "payload": {"choice": "rock"}}
               for agent in tick["agents"])
    assert all("score" in agent["status"] for agent in tick["agents"])
    assert tick["events"][0]["kind"] == "round_result"


def test_pause_unknown_run_raises(mgr):
    with pytest.raises(KeyError):
        mgr.pause_run("nope")


def test_default_agent_factory_builds_llm_sim_agent(tmp_path):
    """Without an explicit agent_factory, the manager must wire up a real
    LLMSimAgent per AgentSpec (using the scenario's action schema) -- this
    is the path actual `sim run` CLI/web usage takes, as opposed to every
    other test in this file which substitutes a scripted factory."""
    from ollama_arena.simulations.agents.llm_agent import LLMSimAgent

    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"))
    agent = mgr._default_agent_factory(
        AgentSpec(agent_id="a", model="llama3.2:3b"), get_scenario("rps"),
    )
    assert isinstance(agent, LLMSimAgent)
    assert agent.model == "llama3.2:3b"
    assert "choose" in agent.action_schema_by_kind


def test_default_agent_factory_without_router_ignores_router_role(tmp_path):
    """No router passed to the manager -- router_role is set on the spec
    but must be a no-op, model resolution stays exactly as before."""
    from ollama_arena.simulations.agents.llm_agent import LLMSimAgent

    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"))
    agent = mgr._default_agent_factory(
        AgentSpec(agent_id="a", model="llama3.2:3b", router_role="npc_dialogue"),
        get_scenario("rps"),
    )
    assert isinstance(agent, LLMSimAgent)
    assert agent.model == "llama3.2:3b"


def test_default_agent_factory_with_router_resolves_model_for_role(tmp_path):
    from ollama_arena.model_router import RoleRouter
    from ollama_arena.simulations.agents.llm_agent import LLMSimAgent

    router = RoleRouter(registry=[], role_models={"npc_dialogue": "qwen3:8b"},
                         local_models=lambda: [])
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), router=router)
    agent = mgr._default_agent_factory(
        AgentSpec(agent_id="a", model="ignored-when-router-role-set", router_role="npc_dialogue"),
        get_scenario("rps"),
    )
    assert isinstance(agent, LLMSimAgent)
    assert agent.model == "qwen3:8b"


def test_default_agent_factory_with_router_but_no_role_keeps_explicit_model(tmp_path):
    """A router is configured, but this particular agent has no
    router_role -- it keeps using its own explicit model, same as the
    no-router case. Mixing routed and pinned agents in one run must work."""
    from ollama_arena.model_router import RoleRouter
    from ollama_arena.simulations.agents.llm_agent import LLMSimAgent

    router = RoleRouter(registry=[], role_models={"npc_dialogue": "qwen3:8b"},
                         local_models=lambda: [])
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), router=router)
    agent = mgr._default_agent_factory(
        AgentSpec(agent_id="a", model="llama3.2:3b"), get_scenario("rps"),
    )
    assert agent.model == "llama3.2:3b"
