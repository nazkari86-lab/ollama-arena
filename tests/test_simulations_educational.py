"""Educational: real built-in tasks, real evaluator scoring, sequential
curriculum progression and graduation."""
import pytest

from ollama_arena.simulations.agents.base import SimAgent
from ollama_arena.simulations.core.runner import SimulationManager
from ollama_arena.simulations.core.types import Action, AgentSpec
from ollama_arena.tasks import get_task


class CorrectAnswerAgent(SimAgent):
    """Looks up the real expected_answer for its current task -- this
    proves the scenario is using the arena's actual evaluator, not a stub,
    since a wrong-looking answer would score 0."""
    def __init__(self, agent_id):
        self.agent_id = agent_id

    def act(self, obs):
        task = obs.status["current_task"]
        if task is None:
            return Action(self.agent_id, "answer", {"answer": ""}, "")
        full = get_task(task["id"])
        return Action(self.agent_id, "answer", {"answer": full.get("expected_answer", "")}, "")


class WrongAnswerAgent(SimAgent):
    def __init__(self, agent_id):
        self.agent_id = agent_id

    def act(self, obs):
        return Action(self.agent_id, "answer", {"answer": "definitely wrong"}, "")


@pytest.fixture
def mgr(tmp_path):
    return SimulationManager(db_path=str(tmp_path / "sim.db"))


def test_correct_answers_score_well_and_agent_graduates(tmp_path):
    agent = CorrectAnswerAgent("a")
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=lambda spec, scenario: agent)
    run_id = mgr.create_run("educational", [AgentSpec(agent_id="a", model="x")],
                             config={"category": "math", "n_tasks": 3}, seed=1)
    result = mgr.start_run(run_id)
    assert result.terminated is True
    assert result.outcome["graduated"] == ["a"]
    assert result.outcome["avg_scores"]["a"] == 1.0
    assert result.metrics["avg_score"] == 1.0
    assert result.metrics["graduation_rate"] == 1.0


def test_wrong_answers_score_zero_but_still_graduate(tmp_path):
    """Graduation depends on reaching the end of the curriculum, not on
    scoring well -- a struggling agent still completes the course."""
    agent = WrongAnswerAgent("a")
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=lambda spec, scenario: agent)
    run_id = mgr.create_run("educational", [AgentSpec(agent_id="a", model="x")],
                             config={"category": "math", "n_tasks": 3}, seed=1)
    result = mgr.start_run(run_id)
    assert result.terminated is True
    assert result.outcome["graduated"] == ["a"]
    assert result.outcome["avg_scores"]["a"] == 0.0


def test_each_tick_presents_the_next_curriculum_task(tmp_path):
    agent = CorrectAnswerAgent("a")
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=lambda spec, scenario: agent)
    run_id = mgr.create_run("educational", [AgentSpec(agent_id="a", model="x")],
                             config={"category": "math", "n_tasks": 3}, seed=1)
    mgr.start_run(run_id)
    answered = [e for e in mgr.store.get_events(run_id) if e.kind == "answered"]
    task_ids = [e.payload["task_id"] for e in answered]
    assert len(set(task_ids)) == 3  # 3 distinct tasks, never repeated


def test_multiple_agents_progress_independently(tmp_path):
    fast = CorrectAnswerAgent("fast")
    slow = WrongAnswerAgent("slow")
    agents = {"fast": fast, "slow": slow}
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=lambda spec, scenario: agents[spec.agent_id])
    run_id = mgr.create_run("educational", [AgentSpec(agent_id="fast", model="x"), AgentSpec(agent_id="slow", model="y")],
                             config={"category": "math", "n_tasks": 2}, seed=1)
    result = mgr.start_run(run_id)
    assert set(result.outcome["graduated"]) == {"fast", "slow"}
    assert result.outcome["avg_scores"]["fast"] == 1.0
    assert result.outcome["avg_scores"]["slow"] == 0.0


def test_unknown_category_raises_clear_error():
    from ollama_arena.simulations.scenarios.educational import EducationalWorld
    with pytest.raises(ValueError, match="no built-in tasks found"):
        EducationalWorld(["a"], config={"category": "definitely_not_a_real_category"})


def test_too_few_agents_raises_at_world_construction():
    from ollama_arena.simulations.scenarios.educational import EducationalWorld
    with pytest.raises(ValueError, match="at least 1"):
        EducationalWorld([])


def test_explicit_curriculum_overrides_category_lookup(tmp_path):
    """A caller-supplied config["curriculum"] (e.g. a hand-picked or
    previously-exported task list, not a real built-in task) must be used
    as-is, without re-deriving it from get_tasks()."""
    custom_task = {"id": "custom_1", "category": "math", "instruction": "Say hello",
                   "expected_answer": "hello", "check": "exact"}

    class SaysHelloAgent(SimAgent):
        agent_id = "a"

        def act(self, obs):
            return Action("a", "answer", {"answer": "hello"}, "")

    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"), agent_factory=lambda spec, scenario: SaysHelloAgent())
    run_id = mgr.create_run("educational", [AgentSpec(agent_id="a", model="x")],
                             config={"curriculum": [custom_task]}, seed=1)
    result = mgr.start_run(run_id)
    assert result.outcome["graduated"] == ["a"]
    assert result.outcome["avg_scores"]["a"] == 1.0
    answered = [e for e in mgr.store.get_events(run_id) if e.kind == "answered"]
    assert answered[0].payload["task_id"] == "custom_1"
