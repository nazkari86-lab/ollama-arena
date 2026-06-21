"""dataset.py: sim.db -> JSONL export round-trip, and the duck-typed
Dataset wrapper -- none of this requires torch installed."""
import pytest

from ollama_arena.simulations.agents.base import SimAgent
from ollama_arena.simulations.core.runner import SimulationManager
from ollama_arena.simulations.core.types import Action, AgentSpec
from ollama_arena.simulations.training.buffer import TrajectoryBuffer
from ollama_arena.simulations.training.dataset import (
    SimTransitionDataset, export_run_to_jsonl, load_jsonl,
)


class _RockAgent(SimAgent):
    def __init__(self, agent_id):
        self.agent_id = agent_id

    def act(self, obs):
        return Action(self.agent_id, "choose", {"choice": "rock"}, "")


class _ScissorsAgent(SimAgent):
    def __init__(self, agent_id):
        self.agent_id = agent_id

    def act(self, obs):
        return Action(self.agent_id, "choose", {"choice": "scissors"}, "")


@pytest.fixture
def populated_db(tmp_path):
    db_path = str(tmp_path / "sim.db")
    agents = {"a": _RockAgent("a"), "b": _ScissorsAgent("b")}
    mgr = SimulationManager(db_path=db_path, agent_factory=lambda spec, scenario: agents[spec.agent_id])
    run_id = mgr.create_run("rps", [AgentSpec(agent_id="a", model="x"), AgentSpec(agent_id="b", model="y")],
                             config={"rounds": 3}, seed=1)
    mgr.start_run(run_id)
    return db_path, run_id


def test_export_run_to_jsonl_writes_one_line_per_transition(tmp_path, populated_db):
    db_path, run_id = populated_db
    out_path = str(tmp_path / "out.jsonl")
    n = export_run_to_jsonl(run_id, out_path, db_path=db_path)
    rows = load_jsonl(out_path)
    assert len(rows) == n
    assert n > 0
    assert all(r["action"]["kind"] == "choose" for r in rows)


def test_export_run_to_jsonl_creates_parent_directories(tmp_path, populated_db):
    db_path, run_id = populated_db
    out_path = str(tmp_path / "nested" / "dir" / "out.jsonl")
    export_run_to_jsonl(run_id, out_path, db_path=db_path)
    assert (tmp_path / "nested" / "dir" / "out.jsonl").exists()


def test_load_jsonl_skips_blank_lines(tmp_path):
    path = tmp_path / "x.jsonl"
    path.write_text('{"a": 1}\n\n{"a": 2}\n')
    rows = load_jsonl(str(path))
    assert rows == [{"a": 1}, {"a": 2}]


def test_dataset_is_indexable_and_sized(tmp_path, populated_db):
    db_path, run_id = populated_db
    out_path = str(tmp_path / "out.jsonl")
    export_run_to_jsonl(run_id, out_path, db_path=db_path)
    ds = SimTransitionDataset(out_path)
    assert len(ds) > 0
    assert ds[0]["action"]["kind"] == "choose"


def test_trajectory_buffer_add_produces_dataset_compatible_rows():
    """The buffer's add() must produce the same row shape
    storage.SimStore.get_transitions() does (via the shared _obs_to_json/
    _action_to_json helpers) -- both feed the same downstream dataset/
    training code, so they must agree."""
    from ollama_arena.simulations.core.types import Action, Observation, Transition
    buf = TrajectoryBuffer()
    assert len(buf) == 0

    obs = Observation(agent_id="a", tick=0, visible_events=())
    action = Action(agent_id="a", kind="choose", payload={"choice": "rock"}, raw_llm_output="{}")
    transition = Transition(tick=1, agent_id="a", obs=obs, action=action, reward=1.0,
                             terminated=False, truncated=False, info={"x": 1})
    buf.add(transition)
    assert len(buf) == 1
    row = buf.rows()[0]
    assert row["action"]["payload"] == {"choice": "rock"}
    assert row["reward"] == 1.0


def test_trajectory_buffer_flush_to_jsonl(tmp_path):
    from ollama_arena.simulations.core.types import Action, Observation, Transition
    buf = TrajectoryBuffer()
    obs = Observation(agent_id="a", tick=0, visible_events=())
    action = Action(agent_id="a", kind="choose", payload={"choice": "rock"}, raw_llm_output="{}")
    buf.add(Transition(tick=1, agent_id="a", obs=obs, action=action, reward=0.0,
                        terminated=False, truncated=False, info={}))
    out_path = str(tmp_path / "buf.jsonl")
    n = buf.flush_to_jsonl(out_path)
    assert n == 1
    rows = load_jsonl(out_path)
    assert len(rows) == 1
