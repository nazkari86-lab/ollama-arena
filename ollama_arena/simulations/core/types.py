"""Shared dataclasses/enums for the simulations engine — no logic here.

These types are the contract every scenario (Mafia, Sims-world, sandbox
universe, ...) is built against, so the core engine never needs scenario-
specific branches. Two rules are encoded directly in the shapes below:

1. An agent's prompt-builder may only ever see an `Observation`, never the
   engine's ground-truth state — `Observation.visible_events` is already
   filtered by `Event.witness_ids` before it reaches agent code.
2. An LLM's raw output is never trusted as an `Action` until it has been
   validated against a scenario's action schema (see action_schema.py);
   `Action.raw_llm_output` keeps the original text around for audit and for
   later imitation-learning datasets.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

AgentId = str

# Sentinel witness set meaning "every agent in the run can see this event."
# A frozenset() (no members) means "nobody but the engine/replay layer sees
# this" -- used internally by the engine, e.g. for derived bookkeeping events.
WITNESS_ALL: frozenset[AgentId] = frozenset({"*"})


class StepMode(str, Enum):
    """How a phase advances: one actor at a time, or everyone at once.

    Mafia's discussion/vote phases are TURN_BASED (one speaker per turn);
    its night phase and every Sims-world daily tick are SIMULTANEOUS (every
    eligible agent acts once per step). A scenario assigns a StepMode per
    phase rather than picking one globally.
    """
    TURN_BASED = "turn_based"
    SIMULTANEOUS = "simultaneous"


@dataclass(frozen=True)
class Event:
    """A single, immutable fact about something that happened in the world.

    `witness_ids` controls visibility: WITNESS_ALL for public events, or an
    explicit subset of agent ids for private ones (e.g. a Mafia-only night
    kill, or a Sims-world private conversation). `World.observe()` is the
    only place this filter is applied -- there is no other path by which an
    agent's observation can include an event it isn't a witness to.
    """
    id: str
    tick: int
    kind: str
    payload: dict[str, Any]
    witness_ids: frozenset[AgentId] = WITNESS_ALL
    actor_id: AgentId | None = None

    def visible_to(self, agent_id: AgentId) -> bool:
        return self.witness_ids == WITNESS_ALL or agent_id in self.witness_ids


@dataclass(frozen=True)
class Observation:
    """What `World.observe(agent_id)` returns -- the only world-state view an
    agent's prompt-builder is allowed to read. Never construct this from
    ground truth directly; always go through the witness-filtered event log.
    """
    agent_id: AgentId
    tick: int
    visible_events: tuple[Event, ...]
    status: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Action:
    """A validated, structured action ready to be applied by `World.step_*()`.

    Only ever constructed by `action_schema.parse_action()` after validating
    raw LLM output against a scenario's schema -- code should never build an
    Action directly from untrusted text.
    """
    agent_id: AgentId
    kind: str
    payload: dict[str, Any]
    raw_llm_output: str = ""


@dataclass(frozen=True)
class Transition:
    """One Gymnasium-style step record: obs -> action -> reward/outcome.

    `terminated` means the episode reached a real terminal state defined by
    the scenario's rules (e.g. one Mafia faction is eliminated); `truncated`
    means the engine cut the episode off for an external reason (e.g. a
    tick budget ran out) before any terminal state was reached. Keeping
    these distinct matters for any later RL/training code that needs to
    avoid bootstrapping value estimates past a real terminal state.
    """
    tick: int
    agent_id: AgentId
    obs: Observation
    action: Action
    reward: float
    terminated: bool
    truncated: bool
    info: dict[str, Any] = field(default_factory=dict)


@dataclass
class EpisodeResult:
    """Summary of one completed (or truncated) simulation run."""
    scenario: str
    run_id: str
    ticks: int
    terminated: bool
    truncated: bool
    outcome: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass
class AgentSpec:
    """What a caller supplies to spin up one agent in a run -- a model name
    plus scenario-specific config (role hints, persona overrides, ...).

    `router_role` is unrelated to scenario role hints in `config` (e.g.
    Mafia's villager/mafia) -- it's one of `model_registry.SIM_ROLES`,
    used only when a `RoleRouter` is passed to `SimulationManager`. When
    set and a router is present, `model` is ignored and the router
    resolves the actual model for this agent instead; default (no
    router, or `router_role=None`) behaves exactly as before."""
    agent_id: AgentId
    model: str
    config: dict[str, Any] = field(default_factory=dict)
    router_role: str | None = None
