"""Mafia -- social deduction with hidden roles.

One round = discussion (turn-based, every living agent speaks once) -> vote
(turn-based, every living agent votes once, ties eliminate nobody) -> night
(simultaneous, living mafia only choose a kill target) -> back to
discussion, until one faction is wiped out or the round budget runs out.

Hidden information is modeled entirely through `Event.witness_ids`, the same
mechanism core/world.py documents: a mafia night-kill decision is recorded
as a private event the mafia faction witnesses, and only a *derived* public
"morning announcement" event (naming who died, not who decided it) is ever
visible to villagers. No special-casing exists anywhere else in the engine
for this -- the witness-filtering in storage.SimStore.get_events() and
World.observe() is exactly the same code path public events use.
"""
from __future__ import annotations

from collections import Counter
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

ROLE_MAFIA = "mafia"
ROLE_VILLAGER = "villager"

PHASE_DISCUSSION = "discussion"
PHASE_VOTE = "vote"
PHASE_NIGHT = "night"


@dataclass
class SpeakAction(ActionSchema):
    # Required, and declared first so the auto-generated JSON example
    # (action_schema_examples()) shows it before the actual decision --
    # nudges even non-reasoning models to write a brief justification
    # before committing, instead of pattern-matching straight to an
    # answer. Recorded on the Action/Transition for replay/eval only; the
    # engine never copies it into a public Event payload (see _emit()
    # calls below), so it cannot change what other agents witness.
    reasoning: str
    text: str


@dataclass
class VoteAction(ActionSchema):
    reasoning: str
    target: str


@dataclass
class NightKillAction(ActionSchema):
    reasoning: str
    target: str | None = None  # None = abstain


_VALID_KINDS_BY_PHASE = {
    PHASE_DISCUSSION: {"speak"},
    PHASE_VOTE: {"vote"},
    PHASE_NIGHT: {"night_kill"},
}

# Role-specific strategic framing, surfaced generically via
# Observation.status["strategy_hint"] (see LLMSimAgent.build_prompt(),
# which treats it as an optional, scenario-agnostic hint -- any scenario
# may set it, not just Mafia). Wording paraphrased from findings in
# "Deceive, Detect, and Disclose: LLMs Play Mini-Mafia" (arXiv:2509.23023)
# and the accompanying github.com/bastoscostadavi/llm-mafia-game
# benchmark: explicit role-specific strategic framing measurably improves
# both deception (mafia) and detection (villagers) quality, compared to a
# bare role label with no guidance.
_STRATEGY_HINT = {
    ROLE_MAFIA: (
        "Keep your story consistent with what you've said in earlier rounds. "
        "Act cooperative and helpful to the village so you don't stand out "
        "as a suspect."
    ),
    ROLE_VILLAGER: (
        "Watch for contradictions between what players say across rounds and "
        "how they vote. Base your suspicion on specific things you've "
        "observed, not just a hunch."
    ),
}


class MafiaWorld(World):
    def __init__(self, agent_ids: list[AgentId], config: dict | None = None):
        if len(agent_ids) < 3:
            raise ValueError("Mafia requires at least 3 agents")
        self.agent_ids = list(agent_ids)
        config = config or {}
        self.max_rounds = config.get("max_rounds") or 20
        # `or` (not .get(key, default)): default_config declares
        # mafia_count=None as documentation of "auto-computed by default" --
        # if that None ever flows through as an actual run config value,
        # .get() would return it as-is and silently skip the computed
        # fallback below.
        self.mafia_count = config.get("mafia_count") or max(1, len(agent_ids) // 3)
        self._event_ids_issued = 0
        self._new_events: list[Event] = []
        self._all_events: list[Event] = []
        self.round = 0
        self.phase = PHASE_DISCUSSION
        self.roles: dict[AgentId, str] = {}
        self.living: set[AgentId] = set()
        self._pending: set[AgentId] = set()
        self._discussion_buffer: dict[AgentId, str] = {}
        self._votes: dict[AgentId, str] = {}
        self._winner_faction: str | None = None

    def _next_event_id(self) -> str:
        self._event_ids_issued += 1
        return f"e{self._event_ids_issued}"

    def _emit(self, kind: str, payload: dict, witness_ids=WITNESS_ALL, actor_id=None) -> Event:
        event = Event(
            id=self._next_event_id(), tick=self.round, kind=kind, payload=payload,
            witness_ids=witness_ids, actor_id=actor_id,
        )
        self._all_events.append(event)
        self._new_events.append(event)
        return event

    # ── lifecycle ────────────────────────────────────────────────────────

    def reset(self, seed: int | None = None) -> dict[AgentId, Observation]:
        ordered = sorted(self.agent_ids)  # deterministic regardless of dict/set ordering
        mafia = set(ordered[: self.mafia_count])
        self.roles = {a: (ROLE_MAFIA if a in mafia else ROLE_VILLAGER) for a in ordered}
        self.living = set(self.agent_ids)
        self.round = 0
        self.phase = PHASE_DISCUSSION
        self._pending = set(self.living)
        self._discussion_buffer = {}
        self._votes = {}
        self._winner_faction = None
        self._all_events = []
        self._new_events = []
        self._event_ids_issued = 0
        return {a: self.observe(a) for a in self.agent_ids}

    def restore_state(self, state: dict) -> None:
        self.round = state["round"]
        self.phase = state["phase"]
        self.roles = dict(state["roles"])
        self.living = set(state["living"])
        self._pending = set(state["pending"])
        self._discussion_buffer = dict(state["discussion_buffer"])
        self._votes = dict(state["votes"])
        self._winner_faction = state.get("winner_faction")
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
        role = self.roles.get(agent_id)
        status: dict = {
            "role": role,
            "alive": agent_id in self.living,
            "phase": self.phase,
            "round": self.round,
        }
        if role in _STRATEGY_HINT:
            status["strategy_hint"] = _STRATEGY_HINT[role]
        if self.roles.get(agent_id) == ROLE_MAFIA:
            status["mafia_team"] = sorted(
                a for a, r in self.roles.items() if r == ROLE_MAFIA and a != agent_id
            )
        if agent_id in self._pending and self.phase in _VALID_KINDS_BY_PHASE:
            status["valid_kinds"] = sorted(_VALID_KINDS_BY_PHASE[self.phase])
        return Observation(agent_id=agent_id, tick=self.round, visible_events=visible, status=status)

    def state(self) -> dict:
        outcome = {}
        if self._winner_faction:
            outcome = {"winner_faction": self._winner_faction, "roles": dict(self.roles),
                       "living": sorted(self.living)}
        return {
            "round": self.round, "phase": self.phase, "roles": dict(self.roles),
            "living": sorted(self.living), "pending": sorted(self._pending),
            "discussion_buffer": dict(self._discussion_buffer), "votes": dict(self._votes),
            "winner_faction": self._winner_faction, "event_ids_issued": self._event_ids_issued,
            "events": [
                {"id": e.id, "tick": e.tick, "kind": e.kind, "payload": e.payload,
                 "witness_ids": sorted(e.witness_ids), "actor_id": e.actor_id}
                for e in self._all_events
            ],
            "outcome": outcome,
        }

    # ── stepping ─────────────────────────────────────────────────────────

    def agent_iter(self) -> Iterator[AgentId]:
        return iter(sorted(self._pending))

    def acting_agents(self) -> set[AgentId] | None:
        if self.phase != PHASE_NIGHT:
            return set()
        return {a for a in self.living if self.roles.get(a) == ROLE_MAFIA}

    def current_step_mode(self) -> StepMode:
        return StepMode.SIMULTANEOUS if self.phase == PHASE_NIGHT else StepMode.TURN_BASED

    def current_phase(self) -> str:
        return self.phase

    def drain_new_events(self) -> list[Event]:
        events, self._new_events = self._new_events, []
        return events

    def step_turn_based(self, agent_id: AgentId, action: Action) -> Transition:
        obs_before = self.observe(agent_id)
        expected_kind = next(iter(_VALID_KINDS_BY_PHASE[self.phase]))
        if action.kind != expected_kind:
            # Engine-level enforcement, defense in depth against an LLM
            # ignoring obs.status["valid_kinds"]: an off-phase action is
            # simply discarded (treated as a pass), not applied.
            self._emit("invalid_action", {"agent": agent_id, "kind": action.kind},
                        witness_ids=frozenset(), actor_id=agent_id)
        elif self.phase == PHASE_DISCUSSION:
            self._discussion_buffer[agent_id] = action.payload.get("text", "")
            self._emit("discussion", {"agent": agent_id, "text": action.payload.get("text", "")},
                        actor_id=agent_id)
        elif self.phase == PHASE_VOTE:
            self._votes[agent_id] = action.payload.get("target")
            self._emit("vote_cast", {"agent": agent_id, "target": action.payload.get("target")},
                        actor_id=agent_id)

        self._pending.discard(agent_id)
        if not self._pending:
            self._finalize_phase()

        return Transition(
            tick=self.round, agent_id=agent_id, obs=obs_before, action=action,
            reward=0.0, terminated=self.is_terminated(), truncated=self.is_truncated(),
            info={},
        )

    def step_simultaneous(self, actions: dict[AgentId, Action]) -> dict[AgentId, Transition]:
        assert self.phase == PHASE_NIGHT
        mafia_ids = sorted(actions)
        obs_before = {aid: self.observe(aid) for aid in mafia_ids}
        targets = [
            a.payload.get("target") for a in actions.values() if a.payload.get("target")
        ]
        killed = None
        if targets:
            killed = Counter(targets).most_common(1)[0][0]
            if killed in self.living:
                self.living.discard(killed)
                mafia_ids_all = frozenset(a for a in self.agent_ids if self.roles.get(a) == ROLE_MAFIA)
                self._emit("night_kill_decided", {"target": killed}, witness_ids=mafia_ids_all)
                self._emit("morning_announcement", {"killed": killed}, witness_ids=WITNESS_ALL)
            else:
                killed = None

        self._check_winner()
        self.round += 1
        if not self.is_terminated():
            self.phase = PHASE_DISCUSSION
            self._pending = set(self.living)
            self._discussion_buffer = {}
            self._votes = {}

        return {
            aid: Transition(
                tick=self.round, agent_id=aid, obs=obs_before[aid], action=actions[aid],
                reward=0.0, terminated=self.is_terminated(), truncated=self.is_truncated(),
                info={"killed": killed},
            )
            for aid in mafia_ids
        }

    def _finalize_phase(self) -> None:
        if self.phase == PHASE_DISCUSSION:
            self.phase = PHASE_VOTE
            self._pending = set(self.living)
        elif self.phase == PHASE_VOTE:
            self._tally_votes()
            self._check_winner()
            if not self.is_terminated():
                self.phase = PHASE_NIGHT
                self._pending = set()  # night uses acting_agents(), not agent_iter()

    def _tally_votes(self) -> None:
        cast = [t for t in self._votes.values() if t]
        eliminated = None
        if cast:
            counts = Counter(cast)
            top_count = max(counts.values())
            top = [a for a, c in counts.items() if c == top_count]
            if len(top) == 1:
                eliminated = top[0]
        if eliminated and eliminated in self.living:
            self.living.discard(eliminated)
            self._emit("elimination", {"eliminated": eliminated, "votes": dict(self._votes)})
        else:
            self._emit("elimination", {"eliminated": None, "votes": dict(self._votes)})

    def _check_winner(self) -> None:
        mafia_alive = {a for a in self.living if self.roles.get(a) == ROLE_MAFIA}
        villagers_alive = self.living - mafia_alive
        if not mafia_alive:
            self._winner_faction = ROLE_VILLAGER
        elif not villagers_alive:
            self._winner_faction = ROLE_MAFIA

    def is_terminated(self) -> bool:
        return self._winner_faction is not None

    def is_truncated(self) -> bool:
        return self.round >= self.max_rounds and self._winner_faction is None


class MafiaScorer(ScenarioScorer):
    def score(self, episode: EpisodeResult) -> dict[str, float]:
        return {
            "resolved": 1.0 if episode.outcome.get("winner_faction") else 0.0,
            "rounds_played": float(episode.ticks),
            "town_won": 1.0 if episode.outcome.get("winner_faction") == ROLE_VILLAGER else 0.0,
        }


register_scenario(ScenarioSpec(
    name="mafia",
    description="Social deduction: hidden mafia minority vs villager majority, "
                 "discussion -> vote -> night cycle.",
    world_factory=MafiaWorld,
    action_schema_by_kind={
        "speak": SpeakAction, "vote": VoteAction, "night_kill": NightKillAction,
    },
    step_mode_by_phase={
        PHASE_DISCUSSION: StepMode.TURN_BASED, PHASE_VOTE: StepMode.TURN_BASED,
        PHASE_NIGHT: StepMode.SIMULTANEOUS,
    },
    default_config={"max_rounds": 20, "mafia_count": None},
    scorer_factory=MafiaScorer,
))
