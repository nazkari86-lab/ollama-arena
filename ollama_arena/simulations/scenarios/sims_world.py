"""Sims-world -- a daily-tick life simulation: every living NPC manages
needs (hunger/energy/social), money, an optional job, and relationships.

Single phase, always simultaneous (every living NPC acts once per day) --
unlike Mafia's multi-phase cycle, there's no turn-based phase here, so
agent_iter() is never actually consumed by the runner. An agent "dies" (is
removed from `living`) if hunger or energy hits zero, which is this
scenario's termination condition: the episode ends once nobody is left
alive, or truncates once the configured day budget runs out with survivors
remaining. Long-running play (many simulated days) is handled entirely by
SimulationManager's existing pause/resume/checkpoint machinery -- this
scenario adds no new persistence code of its own.
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
from ..world.economy import apply_daily_decay, apply_rest, apply_socialize, apply_spend, apply_work, is_starving_to_death
from ..world.entities import NPCStatus
from ..world.relationships import RelationshipGraph

PHASE_DAILY_TICK = "daily_tick"


@dataclass
class WorkAction(ActionSchema):
    pass


@dataclass
class RestAction(ActionSchema):
    pass


@dataclass
class SocializeAction(ActionSchema):
    target: str


@dataclass
class SpendAction(ActionSchema):
    amount: float
    on: str = "food"


class SimsWorldWorld(World):
    def __init__(self, agent_ids: list[AgentId], config: dict | None = None):
        if not agent_ids:
            raise ValueError("Sims-world requires at least 1 agent")
        self.agent_ids = list(agent_ids)
        config = config or {}
        self.max_days = config.get("max_days") or 30
        self._jobs: dict[AgentId, str] = config.get("jobs") or {}
        self._event_ids_issued = 0
        self._new_events: list[Event] = []
        self._all_events: list[Event] = []
        self.day = 0
        self.living: set[AgentId] = set()
        self.statuses: dict[AgentId, NPCStatus] = {}
        self.relationships = RelationshipGraph()

    def _next_event_id(self) -> str:
        self._event_ids_issued += 1
        return f"e{self._event_ids_issued}"

    def _emit(self, kind: str, payload: dict, witness_ids=WITNESS_ALL, actor_id=None) -> Event:
        event = Event(
            id=self._next_event_id(), tick=self.day, kind=kind, payload=payload,
            witness_ids=witness_ids, actor_id=actor_id,
        )
        self._all_events.append(event)
        self._new_events.append(event)
        return event

    # ── lifecycle ────────────────────────────────────────────────────────

    def reset(self, seed: int | None = None) -> dict[AgentId, Observation]:
        self.day = 0
        self.living = set(self.agent_ids)
        self.statuses = {
            aid: NPCStatus(agent_id=aid, job=self._jobs.get(aid)) for aid in self.agent_ids
        }
        self.relationships = RelationshipGraph()
        self._all_events = []
        self._new_events = []
        self._event_ids_issued = 0
        return {a: self.observe(a) for a in self.agent_ids}

    def restore_state(self, state: dict) -> None:
        self.day = state["day"]
        self.living = set(state["living"])
        self.statuses = {aid: NPCStatus.from_dict(d) for aid, d in state["statuses"].items()}
        self.relationships = RelationshipGraph.from_dict(state["relationships"])
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
        status = self.statuses[agent_id].to_dict()
        status["alive"] = agent_id in self.living
        status["day"] = self.day
        status["relationships"] = self.relationships.edges_for(agent_id)
        return Observation(agent_id=agent_id, tick=self.day, visible_events=visible, status=status)

    def state(self) -> dict:
        return {
            "day": self.day, "living": sorted(self.living),
            "statuses": {aid: s.to_dict() for aid, s in self.statuses.items()},
            "relationships": self.relationships.to_dict(),
            "event_ids_issued": self._event_ids_issued,
            "events": [
                {"id": e.id, "tick": e.tick, "kind": e.kind, "payload": e.payload,
                 "witness_ids": sorted(e.witness_ids), "actor_id": e.actor_id}
                for e in self._all_events
            ],
            "outcome": {
                "survivors": sorted(self.living), "all_dead": not bool(self.living),
                "days": self.day,
            },
        }

    # ── stepping ─────────────────────────────────────────────────────────

    def agent_iter(self) -> Iterator[AgentId]:
        return iter(())  # Sims-world never uses turn-based stepping

    def acting_agents(self) -> set[AgentId] | None:
        return set(self.living)

    def current_step_mode(self) -> StepMode:
        return StepMode.SIMULTANEOUS

    def current_phase(self) -> str:
        return PHASE_DAILY_TICK

    def drain_new_events(self) -> list[Event]:
        events, self._new_events = self._new_events, []
        return events

    def step_turn_based(self, agent_id: AgentId, action: Action) -> Transition:
        raise NotImplementedError("Sims-world only steps simultaneously")

    def step_simultaneous(self, actions: dict[AgentId, Action]) -> dict[AgentId, Transition]:
        obs_before = {aid: self.observe(aid) for aid in actions}

        for aid, action in actions.items():
            status = self.statuses[aid]
            kind = action.kind
            if kind == "work":
                wage = apply_work(status)
                self._emit("worked", {"agent": aid, "wage": wage}, actor_id=aid)
            elif kind == "rest":
                apply_rest(status)
                self._emit("rested", {"agent": aid}, actor_id=aid)
            elif kind == "socialize":
                target = action.payload.get("target")
                if target and target in self.living and target != aid:
                    apply_socialize(status)
                    self.relationships.bump(aid, target, 10.0)
                    self._emit("socialized", {"agent": aid, "target": target}, actor_id=aid)
                else:
                    self._emit("invalid_action", {"agent": aid, "kind": kind},
                                witness_ids=frozenset(), actor_id=aid)
            elif kind == "spend":
                amount = action.payload.get("amount", 0.0)
                on = action.payload.get("on", "")
                if apply_spend(status, amount, on):
                    self._emit("spent", {"agent": aid, "amount": amount, "on": on}, actor_id=aid)
                else:
                    self._emit("invalid_action", {"agent": aid, "kind": kind},
                                witness_ids=frozenset(), actor_id=aid)
            else:
                self._emit("invalid_action", {"agent": aid, "kind": kind},
                            witness_ids=frozenset(), actor_id=aid)

        died_this_tick = []
        for aid in list(self.living):
            apply_daily_decay(self.statuses[aid])
            if is_starving_to_death(self.statuses[aid]):
                self.living.discard(aid)
                died_this_tick.append(aid)
        for aid in died_this_tick:
            self._emit("agent_died", {"agent": aid}, witness_ids=WITNESS_ALL)

        self.day += 1

        return {
            aid: Transition(
                tick=self.day, agent_id=aid, obs=obs_before[aid], action=actions[aid],
                reward=0.0, terminated=self.is_terminated(), truncated=self.is_truncated(),
                info={"died": aid in died_this_tick},
            )
            for aid in actions
        }

    def is_terminated(self) -> bool:
        return len(self.living) == 0

    def is_truncated(self) -> bool:
        return self.day >= self.max_days and bool(self.living)


class SimsWorldScorer(ScenarioScorer):
    def score(self, episode: EpisodeResult) -> dict[str, float]:
        outcome = episode.outcome
        return {
            "survivors": float(len(outcome.get("survivors", []))),
            "all_dead": 1.0 if outcome.get("all_dead") else 0.0,
            "days_survived": float(episode.ticks),
        }


register_scenario(ScenarioSpec(
    name="sims_world",
    description="Life simulation: NPCs manage needs, money, jobs, and "
                 "relationships across daily ticks.",
    world_factory=SimsWorldWorld,
    action_schema_by_kind={
        "work": WorkAction, "rest": RestAction, "socialize": SocializeAction,
        "spend": SpendAction,
    },
    step_mode_by_phase={PHASE_DAILY_TICK: StepMode.SIMULTANEOUS},
    default_config={"max_days": 30},
    scorer_factory=SimsWorldScorer,
))
