"""Rock-Paper-Scissors -- the Phase 1 checkpoint scenario.

Deliberately trivial: two agents, one action kind, simultaneous-only
stepping, a one-line win rule. Exists purely to prove the core engine
(turn/step modes, action validation, persistence, replay, scoring) works
end-to-end before any domain complexity (Mafia's hidden roles, Sims-world's
needs/schedules) is layered on top. If a bug shows up in this scenario, it's
a core-engine bug, not a scenario bug -- that's the whole point of having it.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Iterator, Literal, Optional

from ..core.action_schema import ActionSchema
from ..core.scenario import ScenarioSpec, register_scenario
from ..core.types import (
    Action, AgentId, EpisodeResult, Event, Observation, StepMode, Transition,
    WITNESS_ALL,
)
from ..core.world import World
from ..eval.scoring import ScenarioScorer

_BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}


@dataclass
class RPSAction(ActionSchema):
    choice: Literal["rock", "paper", "scissors"]


class RPSWorld(World):
    def __init__(self, agent_ids: list[AgentId], config: dict | None = None):
        if len(agent_ids) != 2:
            raise ValueError("RPS requires exactly 2 agents")
        self.agent_ids = list(agent_ids)
        self.rounds = (config or {}).get("rounds", 3)
        self._event_ids = itertools.count()
        self._new_events: list[Event] = []
        self._all_events: list[Event] = []
        self.round = 0
        self.scores = {a: 0 for a in self.agent_ids}
        self._winner: AgentId | None = None

    def reset(self, seed: int | None = None) -> dict[AgentId, Observation]:
        self.round = 0
        self.scores = {a: 0 for a in self.agent_ids}
        self._winner = None
        self._all_events = []
        self._new_events = []
        return {a: self.observe(a) for a in self.agent_ids}

    def restore_state(self, state: dict) -> None:
        self.round = state["round"]
        self.scores = dict(state["scores"])
        self._winner = state.get("winner")
        self._all_events = [
            Event(id=e["id"], tick=e["tick"], kind=e["kind"], payload=e["payload"],
                  witness_ids=frozenset(e["witness_ids"]), actor_id=e.get("actor_id"))
            for e in state.get("events", [])
        ]

    def observe(self, agent_id: AgentId) -> Observation:
        visible = tuple(e for e in self._all_events if e.visible_to(agent_id))
        return Observation(
            agent_id=agent_id, tick=self.round, visible_events=visible,
            status={"score": self.scores[agent_id], "round": self.round},
        )

    def state(self) -> dict:
        return {
            "round": self.round, "scores": dict(self.scores), "winner": self._winner,
            "events": [
                {"id": e.id, "tick": e.tick, "kind": e.kind, "payload": e.payload,
                 "witness_ids": sorted(e.witness_ids), "actor_id": e.actor_id}
                for e in self._all_events
            ],
            "outcome": {"winner": self._winner, "scores": dict(self.scores)} if self._winner else {},
        }

    def step_turn_based(self, agent_id: AgentId, action: Action):
        raise NotImplementedError("RPS only steps simultaneously")

    def step_simultaneous(self, actions: dict[AgentId, Action]):
        choices: dict[AgentId, Optional[str]] = {aid: a.payload.get("choice") for aid, a in actions.items()}
        a, b = self.agent_ids
        ca, cb = choices.get(a), choices.get(b)
        if ca == cb:
            outcome = "draw"
        elif ca is not None and _BEATS.get(ca) == cb:
            outcome = a
            self.scores[a] += 1
        else:
            outcome = b
            self.scores[b] += 1

        event = Event(
            id=f"e{next(self._event_ids)}", tick=self.round, kind="round_result",
            payload={"choices": choices, "outcome": outcome}, witness_ids=WITNESS_ALL,
        )
        self._all_events.append(event)
        self._new_events.append(event)
        self.round += 1

        majority = self.rounds // 2 + 1
        for aid, score in self.scores.items():
            if score >= majority:
                self._winner = aid

        transitions = {}
        for aid in self.agent_ids:
            transitions[aid] = Transition(
                tick=self.round, agent_id=aid, obs=self.observe(aid),
                action=actions[aid], reward=1.0 if outcome == aid else 0.0,
                terminated=self.is_terminated(), truncated=self.is_truncated(),
                info={"round_outcome": outcome},
            )
        return transitions

    def agent_iter(self) -> Iterator[AgentId]:
        return iter(self.agent_ids)

    def is_terminated(self) -> bool:
        return self._winner is not None

    def is_truncated(self) -> bool:
        return self.round >= self.rounds and self._winner is None

    def current_step_mode(self) -> StepMode:
        return StepMode.SIMULTANEOUS

    def current_phase(self) -> str:
        return "round"

    def drain_new_events(self) -> list[Event]:
        events, self._new_events = self._new_events, []
        return events


class RPSScorer(ScenarioScorer):
    def score(self, episode: EpisodeResult) -> dict[str, float]:
        winner = episode.outcome.get("winner")
        return {
            "resolved": 1.0 if winner else 0.0,
            "rounds_played": float(episode.ticks),
        }


register_scenario(ScenarioSpec(
    name="rps",
    description="Rock-Paper-Scissors -- best-of-N, two agents, simultaneous play.",
    world_factory=RPSWorld,
    action_schema_by_kind={"choose": RPSAction},
    step_mode_by_phase={"round": StepMode.SIMULTANEOUS},
    default_config={"rounds": 3},
    scorer_factory=RPSScorer,
))
