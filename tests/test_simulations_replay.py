"""ReplayPlayer: read-only inspection of a stored run's event log, with
optional per-agent witness filtering."""
import pytest

from ollama_arena.simulations.core.types import Event, WITNESS_ALL
from ollama_arena.simulations.replay.player import ReplayPlayer
from ollama_arena.simulations.storage import SimStore


@pytest.fixture
def run_with_events(tmp_path):
    db_path = str(tmp_path / "sim.db")
    store = SimStore(db_path)
    run_id = store.create_run("mafia", [], {})
    public = Event(id="e1", tick=0, kind="discussion", payload={"text": "hi"}, witness_ids=WITNESS_ALL)
    private = Event(id="e2", tick=0, kind="night_kill", payload={}, witness_ids=frozenset({"mafia_1"}))
    public2 = Event(id="e3", tick=1, kind="announcement", payload={}, witness_ids=WITNESS_ALL)
    store.append_events(run_id, [public, private, public2])
    return db_path, run_id


def test_step_yields_events_in_order_then_none(run_with_events):
    db_path, run_id = run_with_events
    player = ReplayPlayer(run_id, db_path=db_path)
    assert player.step().id == "e1"
    assert player.step().id == "e2"
    assert player.step().id == "e3"
    assert player.step() is None


def test_witness_filter_excludes_events_not_witnessed(run_with_events):
    db_path, run_id = run_with_events
    villager_view = ReplayPlayer(run_id, db_path=db_path, witness_id="villager_1")
    ids = [e.id for e in villager_view.all_events()]
    assert ids == ["e1", "e3"]  # never e2, the mafia-only night kill

    mafia_view = ReplayPlayer(run_id, db_path=db_path, witness_id="mafia_1")
    assert [e.id for e in mafia_view.all_events()] == ["e1", "e2", "e3"]


def test_seek_returns_cumulative_events_up_to_tick(run_with_events):
    db_path, run_id = run_with_events
    player = ReplayPlayer(run_id, db_path=db_path)
    at_tick_0 = player.seek(0)
    assert [e.id for e in at_tick_0] == ["e1", "e2"]
    # step() continues from where seek() left the cursor
    assert player.step().id == "e3"


def test_reset_rewinds_to_start(run_with_events):
    db_path, run_id = run_with_events
    player = ReplayPlayer(run_id, db_path=db_path)
    player.step()
    player.step()
    player.reset()
    assert player.step().id == "e1"


def test_len_reports_event_count(run_with_events):
    db_path, run_id = run_with_events
    assert len(ReplayPlayer(run_id, db_path=db_path)) == 3
    assert len(ReplayPlayer(run_id, db_path=db_path, witness_id="villager_1")) == 2
