"""Sandbox universe -- a generic, config-driven scenario with no built-in
win condition: agents gather and give arbitrary named resources.

Exists to prove the registry/engine handle a fully custom ruleset purely
through config (`config["resources"]` names whatever resources this
particular run cares about) without any engine-level changes -- nothing
here is hardcoded to a specific resource name or rule beyond "gather adds,
give transfers." Open-ended by design: is_terminated() is always False,
matching the "open-ended scenarios, emergent behavior" requirement; an
episode only ever truncates once its tick budget runs out.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from ..core.action_schema import ActionSchema
from ..core.scenario import ScenarioSpec, register_scenario
from ..core.types import (
    Action, AgentId, EpisodeResult, Event, Observation, StepMode, Transition,
    WITNESS_ALL,
)
from ..core.world import World
from ..eval.scoring import ScenarioScorer

PHASE_TICK = "tick"
DEFAULT_RESOURCES = ("wood", "food")
DEFAULT_GATHER_AMOUNT = 1.0


@dataclass
class GatherAction(ActionSchema):
    resource: str


@dataclass
class GiveAction(ActionSchema):
    target: str
    resource: str
    amount: float


class SandboxUniverseWorld(World):
    def __init__(self, agent_ids: list[AgentId], config: dict | None = None):
        if not agent_ids:
            raise ValueError("Sandbox universe requires at least 1 agent")
        self.agent_ids = list(agent_ids)
        config = config or {}
        self.resource_names = list(config.get("resources") or DEFAULT_RESOURCES)
        self.max_ticks = config.get("max_ticks") or 20
        self.gather_amount = config.get("gather_amount") or DEFAULT_GATHER_AMOUNT
        self._event_ids_issued = 0
        self._new_events: list[Event] = []
        self._all_events: list[Event] = []
        self.tick_count = 0
        self.living: set[AgentId] = set()
        self.resources: dict[AgentId, dict[str, float]] = {}

    def _next_event_id(self) -> str:
        self._event_ids_issued += 1
        return f"e{self._event_ids_issued}"

    def _emit(self, kind: str, payload: dict, witness_ids=WITNESS_ALL, actor_id=None) -> Event:
        event = Event(
            id=self._next_event_id(), tick=self.tick_count, kind=kind, payload=payload,
            witness_ids=witness_ids, actor_id=actor_id,
        )
        self._all_events.append(event)
        self._new_events.append(event)
        return event

    # ── lifecycle ────────────────────────────────────────────────────────

    def reset(self, seed: int | None = None) -> dict[AgentId, Observation]:
        self.tick_count = 0
        self.living = set(self.agent_ids)
        self.resources = {aid: {r: 0.0 for r in self.resource_names} for aid in self.agent_ids}
        self._all_events = []
        self._new_events = []
        self._event_ids_issued = 0
        return {a: self.observe(a) for a in self.agent_ids}

    def restore_state(self, state: dict) -> None:
        self.tick_count = state["tick"]
        self.living = set(state["living"])
        self.resources = {aid: dict(r) for aid, r in state["resources"].items()}
        self._event_ids_issued = state["event_ids_issued"]
        self._all_events = [
            Event(id=e["id"], tick=e["tick"], kind=e["kind"], payload=e["payload"],
                  witness_ids=frozenset(e["witness_ids"]), actor_id=e.get("actor_id"))
            for e in state["events"]
        ]
        self._new_events = []

    # ── observation / ground truth ──────────────────────────────────────

    def observe(self, agent_id: AgentId) -> Observation:
        visible = tuple(e for e in self._all_events if e.visible_to(agent_id))
        status = {
            "alive": agent_id in self.living, "tick": self.tick_count,
            "resources": dict(self.resources.get(agent_id, {})),
        }
        return Observation(agent_id=agent_id, tick=self.tick_count, visible_events=visible, status=status)

    def state(self) -> dict:
        return {
            "tick": self.tick_count, "living": sorted(self.living),
            "resources": {aid: dict(r) for aid, r in self.resources.items()},
            "event_ids_issued": self._event_ids_issued,
            "events": [
                {"id": e.id, "tick": e.tick, "kind": e.kind, "payload": e.payload,
                 "witness_ids": sorted(e.witness_ids), "actor_id": e.actor_id}
                for e in self._all_events
            ],
            "outcome": {
                "total_gathered": sum(
                    sum(r.values()) for r in self.resources.values()
                ),
                "ticks": self.tick_count,
            },
        }

    # ── stepping ─────────────────────────────────────────────────────────

    def agent_iter(self) -> Iterator[AgentId]:
        return iter(())  # always simultaneous

    def acting_agents(self) -> set[AgentId] | None:
        return set(self.living)

    def current_step_mode(self) -> StepMode:
        return StepMode.SIMULTANEOUS

    def current_phase(self) -> str:
        return PHASE_TICK

    def drain_new_events(self) -> list[Event]:
        events, self._new_events = self._new_events, []
        return events

    def step_turn_based(self, agent_id: AgentId, action: Action) -> Transition:
        raise NotImplementedError("Sandbox universe only steps simultaneously")

    def step_simultaneous(self, actions: dict[AgentId, Action]) -> dict[AgentId, Transition]:
        obs_before = {aid: self.observe(aid) for aid in actions}

        for aid, action in actions.items():
            if action.kind == "gather":
                resource = action.payload.get("resource")
                if resource is not None and resource in self.resource_names:
                    self.resources[aid][resource] += self.gather_amount
                    self._emit("gathered", {"agent": aid, "resource": resource}, actor_id=aid)
                else:
                    self._emit("invalid_action", {"agent": aid, "kind": "gather"},
                                witness_ids=frozenset(), actor_id=aid)
            elif action.kind == "give":
                target = action.payload.get("target")
                resource = action.payload.get("resource")
                amount = action.payload.get("amount", 0.0)
                can_give = (
                    target is not None and resource is not None
                    and target in self.living and target != aid
                    and resource in self.resource_names
                    and 0 < amount <= self.resources[aid].get(resource, 0.0)
                )
                if can_give:
                    assert target is not None and resource is not None  # implied by can_give
                    self.resources[aid][resource] -= amount
                    self.resources[target][resource] += amount
                    self._emit("gave", {"agent": aid, "target": target,
                                         "resource": resource, "amount": amount}, actor_id=aid)
                else:
                    self._emit("invalid_action", {"agent": aid, "kind": "give"},
                                witness_ids=frozenset(), actor_id=aid)
            else:
                self._emit("invalid_action", {"agent": aid, "kind": action.kind},
                            witness_ids=frozenset(), actor_id=aid)

        self.tick_count += 1

        return {
            aid: Transition(
                tick=self.tick_count, agent_id=aid, obs=obs_before[aid], action=actions[aid],
                reward=0.0, terminated=self.is_terminated(), truncated=self.is_truncated(),
                info={},
            )
            for aid in actions
        }

    def is_terminated(self) -> bool:
        return False  # open-ended by design -- only ever truncates

    def is_truncated(self) -> bool:
        return self.tick_count >= self.max_ticks


class SandboxUniverseScorer(ScenarioScorer):
    def score(self, episode: EpisodeResult) -> dict[str, float]:
        return {
            "total_gathered": float(episode.outcome.get("total_gathered", 0.0)),
            "ticks": float(episode.ticks),
        }


register_scenario(ScenarioSpec(
    name="sandbox_universe",
    description="Generic, config-driven sandbox: agents gather and give "
                 "arbitrary named resources with no built-in win condition.",
    world_factory=SandboxUniverseWorld,
    action_schema_by_kind={"gather": GatherAction, "give": GiveAction},
    step_mode_by_phase={PHASE_TICK: StepMode.SIMULTANEOUS},
    default_config={"resources": list(DEFAULT_RESOURCES), "max_ticks": 20},
    scorer_factory=SandboxUniverseScorer,
))
