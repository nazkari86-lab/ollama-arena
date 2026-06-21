"""Game-playing -- abstract strategy games, generalizing the Phase 1 RPS
checkpoint scenario into a richer turn-based game: Tic-Tac-Toe.

Strictly alternating turns: agent_iter() yields exactly the single agent
whose move it is, so one engine tick == one placed mark (unlike Mafia's
discussion/vote phases, where one tick == every living agent acting once).
This is the natural target for training.selfplay's eventual self-play loop
(stubbed in Phase 4): two copies of the same trained checkpoint, alternating
moves against each other.
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

PHASE_PLAY = "play"

_WIN_LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),  # rows
    (0, 3, 6), (1, 4, 7), (2, 5, 8),  # columns
    (0, 4, 8), (2, 4, 6),             # diagonals
]


@dataclass
class PlaceAction(ActionSchema):
    cell: int


class TicTacToeWorld(World):
    def __init__(self, agent_ids: list[AgentId], config: dict | None = None):
        if len(agent_ids) != 2:
            raise ValueError("Tic-Tac-Toe requires exactly 2 agents")
        self.agent_ids = list(agent_ids)
        self._event_ids_issued = 0
        self._new_events: list[Event] = []
        self._all_events: list[Event] = []
        self.move_count = 0
        self.board: list[AgentId | None] = [None] * 9
        self.current_agent: AgentId = self.agent_ids[0]
        self._winner: AgentId | None = None
        self._draw = False

    def _next_event_id(self) -> str:
        self._event_ids_issued += 1
        return f"e{self._event_ids_issued}"

    def _emit(self, kind: str, payload: dict, witness_ids=WITNESS_ALL, actor_id=None) -> Event:
        event = Event(
            id=self._next_event_id(), tick=self.move_count, kind=kind, payload=payload,
            witness_ids=witness_ids, actor_id=actor_id,
        )
        self._all_events.append(event)
        self._new_events.append(event)
        return event

    # ── lifecycle ────────────────────────────────────────────────────────

    def reset(self, seed: int | None = None) -> dict[AgentId, Observation]:
        self.move_count = 0
        self.board = [None] * 9
        self.current_agent = self.agent_ids[0]
        self._winner = None
        self._draw = False
        self._all_events = []
        self._new_events = []
        self._event_ids_issued = 0
        return {a: self.observe(a) for a in self.agent_ids}

    def restore_state(self, state: dict) -> None:
        self.move_count = state["move_count"]
        self.board = list(state["board"])
        self.current_agent = state["current_agent"]
        self._winner = state.get("winner")
        self._draw = state.get("draw", False)
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
            "board": list(self.board), "your_turn": agent_id == self.current_agent,
            "move_count": self.move_count,
        }
        return Observation(agent_id=agent_id, tick=self.move_count, visible_events=visible, status=status)

    def state(self) -> dict:
        outcome = {}
        if self._winner or self._draw:
            outcome = {"winner": self._winner, "draw": self._draw, "board": list(self.board)}
        return {
            "move_count": self.move_count, "board": list(self.board),
            "current_agent": self.current_agent, "winner": self._winner, "draw": self._draw,
            "event_ids_issued": self._event_ids_issued,
            "events": [
                {"id": e.id, "tick": e.tick, "kind": e.kind, "payload": e.payload,
                 "witness_ids": sorted(e.witness_ids), "actor_id": e.actor_id}
                for e in self._all_events
            ],
            "outcome": outcome,
        }

    # ── stepping ─────────────────────────────────────────────────────────

    def agent_iter(self) -> Iterator[AgentId]:
        return iter([self.current_agent])

    def current_step_mode(self) -> StepMode:
        return StepMode.TURN_BASED

    def current_phase(self) -> str:
        return PHASE_PLAY

    def drain_new_events(self) -> list[Event]:
        events, self._new_events = self._new_events, []
        return events

    def step_simultaneous(self, actions: dict[AgentId, Action]) -> dict[AgentId, Transition]:
        raise NotImplementedError("Tic-Tac-Toe only steps turn-based")

    def step_turn_based(self, agent_id: AgentId, action: Action) -> Transition:
        obs_before = self.observe(agent_id)
        cell = action.payload.get("cell")
        if action.kind != "place" or not isinstance(cell, int) or not (0 <= cell < 9) or self.board[cell] is not None:
            self._emit("invalid_action", {"agent": agent_id, "kind": action.kind},
                        witness_ids=frozenset(), actor_id=agent_id)
        else:
            self.board[cell] = agent_id
            self._emit("placed", {"agent": agent_id, "cell": cell}, actor_id=agent_id)
            self._check_winner()
            if not self._winner and any(c is None for c in self.board):
                self.current_agent = self.agent_ids[1] if agent_id == self.agent_ids[0] else self.agent_ids[0]
            elif not self._winner:
                self._draw = True

        self.move_count += 1

        return Transition(
            tick=self.move_count, agent_id=agent_id, obs=obs_before, action=action,
            reward=1.0 if self._winner == agent_id else 0.0,
            terminated=self.is_terminated(), truncated=self.is_truncated(), info={},
        )

    def _check_winner(self) -> None:
        for a, b, c in _WIN_LINES:
            if self.board[a] is not None and self.board[a] == self.board[b] == self.board[c]:
                self._winner = self.board[a]
                return

    def is_terminated(self) -> bool:
        return self._winner is not None or self._draw

    def is_truncated(self) -> bool:
        return self.move_count >= 9 and not self.is_terminated()


class TicTacToeScorer(ScenarioScorer):
    def score(self, episode: EpisodeResult) -> dict[str, float]:
        return {
            "resolved": 1.0 if episode.outcome.get("winner") else 0.0,
            "draw": 1.0 if episode.outcome.get("draw") else 0.0,
            "moves": float(episode.ticks),
        }


register_scenario(ScenarioSpec(
    name="tictactoe",
    description="Abstract strategy game-playing: Tic-Tac-Toe, strictly "
                 "alternating turns, model-vs-model.",
    world_factory=TicTacToeWorld,
    action_schema_by_kind={"place": PlaceAction},
    step_mode_by_phase={PHASE_PLAY: StepMode.TURN_BASED},
    default_config={},
    scorer_factory=TicTacToeScorer,
))
