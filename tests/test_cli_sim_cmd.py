"""Tests for cli/sim_cmd.py -- exercised against the real SimulationManager
+ rps scenario with a scripted agent factory, so no real/mocked LLM calls
are needed and these tests stay fast and deterministic."""
from __future__ import annotations

import unittest.mock as mock

import pytest

from ollama_arena.simulations.agents.base import SimAgent
from ollama_arena.simulations.core.runner import SimulationManager
from ollama_arena.simulations.core.types import Action


class _RockAgent(SimAgent):
    def __init__(self, agent_id):
        self.agent_id = agent_id

    def act(self, obs):
        return Action(self.agent_id, "choose", {"choice": "rock"}, "")


def _scripted_manager(db_path):
    return SimulationManager(db_path=db_path, agent_factory=lambda spec, scenario: _RockAgent(spec.agent_id))


def _make_args(**kwargs):
    args = mock.MagicMock()
    args.sim_db = "sim.db"
    args.sim_cmd = None
    args.config = None
    args.seed = None
    args.ticks = 10
    for k, v in kwargs.items():
        setattr(args, k, v)
    return args


def test_agent_specs_from_models_dedupes_with_suffix():
    from ollama_arena.cli.sim_cmd import _agent_specs_from_models
    specs = _agent_specs_from_models(["llama3.2:3b", "llama3.2:3b", "qwen2.5:7b"])
    ids = [s.agent_id for s in specs]
    assert ids == ["llama3.2:3b", "llama3.2:3b_2", "qwen2.5:7b"]
    assert all(s.model in ("llama3.2:3b", "qwen2.5:7b") for s in specs)


def test_load_config_returns_empty_dict_when_no_path():
    from ollama_arena.cli.sim_cmd import _load_config
    assert _load_config(None) == {}


def test_load_config_reads_json(tmp_path):
    from ollama_arena.cli.sim_cmd import _load_config
    path = tmp_path / "cfg.json"
    path.write_text('{"rounds": 5}')
    assert _load_config(str(path)) == {"rounds": 5}


def test_cmd_sim_list_prints_table():
    from ollama_arena.cli.sim_cmd import cmd_sim
    mock_console = mock.MagicMock()
    args = _make_args(sim_cmd="list")
    with mock.patch("ollama_arena.cli.sim_cmd._console", return_value=mock_console):
        cmd_sim(args)
    mock_console.print.assert_called_once()


def test_cmd_sim_run_creates_and_starts_a_run(tmp_path):
    from ollama_arena.cli.sim_cmd import cmd_sim
    mock_console = mock.MagicMock()
    args = _make_args(sim_cmd="run", scenario="rps", agents="a,b", ticks=10, sim_db=str(tmp_path / "sim.db"))
    mgr = _scripted_manager(args.sim_db)
    with mock.patch("ollama_arena.cli.sim_cmd._console", return_value=mock_console), \
         mock.patch("ollama_arena.cli.sim_cmd._make_manager", return_value=mgr):
        cmd_sim(args)
    printed = " ".join(str(c) for c in mock_console.print.call_args_list)
    assert "Run created" in printed
    assert len(mgr.list_runs()) == 1


def test_cmd_sim_inspect_unknown_run_prints_warning(tmp_path):
    from ollama_arena.cli.sim_cmd import cmd_sim
    mock_console = mock.MagicMock()
    args = _make_args(sim_cmd="inspect", run_id="does_not_exist", sim_db=str(tmp_path / "sim.db"))
    mgr = _scripted_manager(args.sim_db)
    with mock.patch("ollama_arena.cli.sim_cmd._console", return_value=mock_console), \
         mock.patch("ollama_arena.cli.sim_cmd._make_manager", return_value=mgr):
        cmd_sim(args)
    printed = " ".join(str(c) for c in mock_console.print.call_args_list)
    assert "No run found" in printed


def test_cmd_sim_inspect_existing_run_prints_status(tmp_path):
    from ollama_arena.cli.sim_cmd import cmd_sim
    mock_console = mock.MagicMock()
    db_path = str(tmp_path / "sim.db")
    mgr = _scripted_manager(db_path)
    from ollama_arena.simulations.core.types import AgentSpec
    run_id = mgr.create_run("rps", [AgentSpec(agent_id="a", model="x"), AgentSpec(agent_id="b", model="y")],
                             config={"rounds": 3}, seed=1)
    mgr.start_run(run_id)

    args = _make_args(sim_cmd="inspect", run_id=run_id, sim_db=db_path)
    with mock.patch("ollama_arena.cli.sim_cmd._console", return_value=mock_console), \
         mock.patch("ollama_arena.cli.sim_cmd._make_manager", return_value=mgr):
        cmd_sim(args)
    printed = " ".join(str(c) for c in mock_console.print.call_args_list)
    assert run_id in printed
    assert "rps" in printed


def test_cmd_sim_replay_unknown_run_prints_warning(tmp_path):
    from ollama_arena.cli.sim_cmd import cmd_sim
    mock_console = mock.MagicMock()
    args = _make_args(sim_cmd="replay", run_id="does_not_exist", tick=None, sim_db=str(tmp_path / "sim.db"))
    with mock.patch("ollama_arena.cli.sim_cmd._console", return_value=mock_console):
        cmd_sim(args)
    printed = " ".join(str(c) for c in mock_console.print.call_args_list)
    assert "No events found" in printed


def test_cmd_sim_replay_existing_run_prints_events(tmp_path):
    from ollama_arena.cli.sim_cmd import cmd_sim
    mock_console = mock.MagicMock()
    db_path = str(tmp_path / "sim.db")
    mgr = _scripted_manager(db_path)
    from ollama_arena.simulations.core.types import AgentSpec
    run_id = mgr.create_run("rps", [AgentSpec(agent_id="a", model="x"), AgentSpec(agent_id="b", model="y")],
                             config={"rounds": 3}, seed=1)
    mgr.start_run(run_id)

    args = _make_args(sim_cmd="replay", run_id=run_id, tick=None, sim_db=db_path)
    with mock.patch("ollama_arena.cli.sim_cmd._console", return_value=mock_console):
        cmd_sim(args)
    printed = " ".join(str(c) for c in mock_console.print.call_args_list)
    assert "round_result" in printed


def test_cmd_sim_train_no_transitions_prints_warning(tmp_path):
    from ollama_arena.cli.sim_cmd import cmd_sim
    mock_console = mock.MagicMock()
    args = _make_args(sim_cmd="train", run_id="does_not_exist", epochs=5, sim_db=str(tmp_path / "sim.db"))
    with mock.patch("ollama_arena.cli.sim_cmd._console", return_value=mock_console):
        cmd_sim(args)
    printed = " ".join(str(c) for c in mock_console.print.call_args_list)
    assert "No transitions found" in printed


def test_cmd_sim_train_single_action_kind_reports_failure_not_crash(tmp_path):
    """rps with both agents always playing rock produces only one action
    kind ('choose') -- train_imitation() correctly refuses (needs >= 2
    kinds to classify), and cmd_sim must report this gracefully, not
    let the ValueError propagate as an uncaught crash."""
    from ollama_arena.cli.sim_cmd import cmd_sim
    mock_console = mock.MagicMock()
    db_path = str(tmp_path / "sim.db")
    mgr = _scripted_manager(db_path)
    from ollama_arena.simulations.core.types import AgentSpec
    run_id = mgr.create_run("rps", [AgentSpec(agent_id="a", model="x"), AgentSpec(agent_id="b", model="y")],
                             config={"rounds": 3}, seed=1)
    mgr.start_run(run_id)

    args = _make_args(sim_cmd="train", run_id=run_id, epochs=3, sim_db=db_path)
    with mock.patch("ollama_arena.cli.sim_cmd._console", return_value=mock_console):
        cmd_sim(args)  # must not raise
    printed = " ".join(str(c) for c in mock_console.print.call_args_list)
    assert "Training failed" in printed


def test_cmd_sim_no_subcommand_prints_usage():
    from ollama_arena.cli.sim_cmd import cmd_sim
    mock_console = mock.MagicMock()
    args = _make_args(sim_cmd=None)
    with mock.patch("ollama_arena.cli.sim_cmd._console", return_value=mock_console):
        cmd_sim(args)
    printed = " ".join(str(c) for c in mock_console.print.call_args_list)
    assert "Usage" in printed
