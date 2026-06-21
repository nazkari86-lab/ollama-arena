"""Tic-Tac-Toe: strict turn alternation, win/draw detection, and the
deliberate "invalid move retries the same agent, never silently advances
the turn" rule."""
import pytest

from ollama_arena.simulations.agents.base import SimAgent
from ollama_arena.simulations.core.runner import SimulationManager
from ollama_arena.simulations.core.types import Action, AgentSpec


class ScriptedAgent(SimAgent):
    def __init__(self, agent_id, cells):
        self.agent_id = agent_id
        self._it = iter(cells)

    def act(self, obs):
        return Action(self.agent_id, "place", {"cell": next(self._it)}, "")


def _run(cells_a, cells_b, tmp_path, **config):
    agents = {"a": ScriptedAgent("a", cells_a), "b": ScriptedAgent("b", cells_b)}
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"),
                             agent_factory=lambda spec, scenario: agents[spec.agent_id])
    run_id = mgr.create_run("tictactoe", [AgentSpec(agent_id="a", model="x"), AgentSpec(agent_id="b", model="y")],
                             config=config, seed=1)
    result = mgr.start_run(run_id)
    return mgr, run_id, result


def test_top_row_wins_for_agent_a(tmp_path):
    mgr, run_id, result = _run([0, 1, 2], [3, 4], tmp_path)
    assert result.terminated is True
    assert result.outcome["winner"] == "a"
    assert result.outcome["draw"] is False


def test_turns_strictly_alternate(tmp_path):
    mgr, run_id, result = _run([0, 1, 2], [3, 4], tmp_path)
    placed = [e for e in mgr.store.get_events(run_id) if e.kind == "placed"]
    actors = [e.payload["agent"] for e in placed]
    assert actors == ["a", "b", "a", "b", "a"]


def test_invalid_move_retries_same_agent_without_advancing_turn(tmp_path):
    """b's first move targets an already-occupied cell -- the engine must
    reject it and ask b again (not silently skip to a)."""
    mgr, run_id, result = _run([0, 1, 2, 3, 4], [0, 3, 4, 5, 6, 7, 8], tmp_path)
    invalid = [e for e in mgr.store.get_events(run_id) if e.kind == "invalid_action"]
    assert len(invalid) == 1
    assert invalid[0].payload["agent"] == "b"
    placed = [e for e in mgr.store.get_events(run_id) if e.kind == "placed"]
    # b's very next placed event (after the invalid one) must still be b,
    # not a -- proving the turn never advanced past the rejected attempt.
    first_after_invalid = placed[1]
    assert first_after_invalid.payload["agent"] == "b"


def test_full_board_no_winner_is_a_draw(tmp_path):
    # Final board (X O X / X O O / O X X) has no 3-in-a-row for either
    # player in any row, column, or diagonal -- a verified draw layout.
    # X (a) ends up in cells {0,2,3,7,8}; O (b) ends up in cells {1,4,5,6}.
    mgr, run_id, result = _run([0, 2, 3, 7, 8], [1, 4, 5, 6], tmp_path)
    assert result.terminated is True
    assert result.outcome["winner"] is None
    assert result.outcome["draw"] is True


def test_observation_never_includes_a_winner_field_pre_game_end(tmp_path):
    """observe() exposes the board (legitimate -- both players always see
    the full board in tic-tac-toe) but state()'s outcome must stay empty
    until the game actually ends -- no early peek at the result."""
    from ollama_arena.simulations.scenarios.game_playing import TicTacToeWorld
    world = TicTacToeWorld(["a", "b"])
    world.reset()
    assert world.state()["outcome"] == {}


def test_too_many_or_few_agents_raises_at_world_construction():
    from ollama_arena.simulations.scenarios.game_playing import TicTacToeWorld
    with pytest.raises(ValueError, match="exactly 2"):
        TicTacToeWorld(["a"])
    with pytest.raises(ValueError, match="exactly 2"):
        TicTacToeWorld(["a", "b", "c"])


def test_pause_then_resume_continues_with_same_board(tmp_path):
    agents = {"a": ScriptedAgent("a", [0, 1, 2]), "b": ScriptedAgent("b", [3, 4])}
    mgr = SimulationManager(db_path=str(tmp_path / "sim.db"),
                             agent_factory=lambda spec, scenario: agents[spec.agent_id])
    run_id = mgr.create_run("tictactoe", [AgentSpec(agent_id="a", model="x"), AgentSpec(agent_id="b", model="y")],
                             config={}, seed=1)

    def stop_after_2(d):
        if d["tick"] >= 2:
            mgr.pause_run(run_id)

    mgr.start_run(run_id, on_tick=stop_after_2)
    assert mgr.get_status(run_id).value == "paused"
    checkpoint = mgr.store.latest_checkpoint(run_id)
    assert checkpoint["state"]["board"][0] == "a"

    result = mgr.resume_run(run_id)
    assert result.terminated is True
    assert result.outcome["winner"] == "a"
