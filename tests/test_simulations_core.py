"""Core types/world contract: the observe()/state() ground-truth split,
event witness filtering, and the registry's anti-footgun guard."""
import inspect
from dataclasses import dataclass

import pytest

from ollama_arena.simulations.core.action_schema import ActionSchema
from ollama_arena.simulations.core.scenario import (
    ScenarioSpec, get_scenario, list_scenarios, register_scenario,
)
from ollama_arena.simulations.core.types import WITNESS_ALL, Event
from ollama_arena.simulations.core.world import World


def test_witness_all_event_visible_to_everyone():
    event = Event(id="e1", tick=0, kind="speak", payload={}, witness_ids=WITNESS_ALL)
    assert event.visible_to("agent_a")
    assert event.visible_to("anyone")


def test_private_event_only_visible_to_witnesses():
    event = Event(id="e1", tick=0, kind="night_kill", payload={},
                  witness_ids=frozenset({"mafia_1", "mafia_2"}))
    assert event.visible_to("mafia_1")
    assert not event.visible_to("villager_1")


def test_engine_only_event_visible_to_nobody():
    """An empty witness set (not WITNESS_ALL) means engine/replay-only --
    no agent, however privileged, should see it via observe()."""
    event = Event(id="e1", tick=0, kind="internal_bookkeeping", payload={},
                   witness_ids=frozenset())
    assert not event.visible_to("mafia_1")
    assert not event.visible_to("anyone")


def test_world_is_abstract_and_enforces_the_full_contract():
    """A World subclass missing any abstract method must fail to
    instantiate -- this is what makes the observe()/state() split (and
    drain_new_events()/restore_state()) a hard contract, not a convention
    a scenario author could accidentally skip."""
    class IncompleteWorld(World):
        def reset(self, seed=None):
            return {}
    with pytest.raises(TypeError):
        IncompleteWorld()


def test_rps_is_registered_via_builtin_import():
    names = {s.name for s in list_scenarios()}
    assert "rps" in names


def test_get_scenario_unknown_name_raises_key_error():
    with pytest.raises(KeyError, match="unknown scenario"):
        get_scenario("does_not_exist")


def test_register_scenario_rejects_duplicate_name():
    spec = get_scenario("rps")
    with pytest.raises(ValueError, match="already registered"):
        register_scenario(spec)


def test_register_scenario_rejects_schema_missing_dataclass_decorator():
    """Regression guard: a per-kind schema that subclasses ActionSchema but
    forgets its own @dataclass decorator silently has zero fields (dataclass-
    ness is not inherited), which would make validate_schema() accept any
    payload for that action kind without checking anything. This must be
    caught at registration time, not discovered later at runtime."""
    class BrokenAction(ActionSchema):
        choice: str

    with pytest.raises(TypeError, match="missing a @dataclass decorator"):
        register_scenario(ScenarioSpec(
            name="_test_broken_schema_scenario",
            description="x",
            world_factory=lambda **k: None,
            action_schema_by_kind={"choose": BrokenAction},
        ))


def test_register_scenario_accepts_properly_decorated_schema():
    @dataclass
    class FineAction(ActionSchema):
        choice: str

    register_scenario(ScenarioSpec(
        name="_test_fine_schema_scenario",
        description="x",
        world_factory=lambda **k: None,
        action_schema_by_kind={"choose": FineAction},
    ))
    assert get_scenario("_test_fine_schema_scenario").name == "_test_fine_schema_scenario"
