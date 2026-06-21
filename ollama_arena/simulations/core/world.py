"""The engine's hard interface contract that every scenario implements.

`observe()` vs `state()` is the load-bearing split in this whole subsystem:
`observe(agent_id)` is the *only* method an agent's prompt-builder may call,
and it returns a witness-filtered view. `state()` returns ground truth and is
reserved for the engine itself, the eval/scoring layer, and replay -- never
for agent-facing code. Concrete scenarios (Mafia, Sims-world, ...) subclass
`World` and are responsible for upholding that split when implementing
`observe()` (i.e. actually filtering through `Event.witness_ids`, not just
returning a trimmed copy of `state()`).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator

from .types import Action, AgentId, Event, Observation, StepMode, Transition


class World(ABC):
    """Base class for a scenario's concrete simulation state + step logic."""

    @abstractmethod
    def reset(self, seed: int | None = None) -> dict[AgentId, Observation]:
        """Reset to a fresh episode, returning each agent's initial observation."""
        ...

    @abstractmethod
    def restore_state(self, state: dict) -> None:
        """Restore from a previously-checkpointed `state()` dict, for
        resuming a paused run without replaying every tick from scratch."""
        ...

    @abstractmethod
    def observe(self, agent_id: AgentId) -> Observation:
        """The only world-state read an agent's prompt-builder may use."""
        ...

    @abstractmethod
    def state(self) -> dict:
        """Ground-truth state. Engine/eval/replay-only -- never agent-facing."""
        ...

    @abstractmethod
    def step_turn_based(self, agent_id: AgentId, action: Action) -> Transition:
        """Apply one agent's action; used for phases where actors act in
        strict sequence (e.g. Mafia's discussion/vote phases)."""
        ...

    @abstractmethod
    def step_simultaneous(self, actions: dict[AgentId, Action]) -> dict[AgentId, Transition]:
        """Apply every given agent's action as one joint step; used for
        phases where actors act at once (e.g. Mafia's night phase, every
        Sims-world daily tick)."""
        ...

    @abstractmethod
    def agent_iter(self) -> Iterator[AgentId]:
        """Yield agent ids in turn order for the current turn-based phase."""
        ...

    @abstractmethod
    def is_terminated(self) -> bool:
        """True once the scenario's own rules define a real terminal state
        (e.g. one Mafia faction eliminated). Distinct from is_truncated()."""
        ...

    @abstractmethod
    def is_truncated(self) -> bool:
        """True once an external limit (tick/step budget) cuts the episode
        short before any terminal state was reached."""
        ...

    @abstractmethod
    def current_step_mode(self) -> StepMode:
        """Which stepping mode the world is currently in -- the runner
        branches on this each tick to call step_turn_based() (draining
        agent_iter()) or step_simultaneous() (every agent at once)."""
        ...

    @abstractmethod
    def current_phase(self) -> str:
        """Human-readable name of the current phase (e.g. "discussion",
        "night", "daily_tick") -- for logging and the dashboard's phase
        timeline. Purely descriptive; the runner never branches on this."""
        ...

    @abstractmethod
    def drain_new_events(self) -> list[Event]:
        """Return and clear events generated since the last call.

        This is the runner's only way to learn what happened during a step,
        for persistence and replay -- observe() must keep relying on the
        world's own internal event log, not this drained buffer, so a late
        drain() call never changes what any agent's observation contains.
        """
        ...

    def acting_agents(self) -> set[AgentId] | None:
        """Which of the registered agents the runner should ask to act on
        the next SIMULTANEOUS step. None (the default) means "everyone."

        Needed once a scenario has a phase where only a subset of agents
        has anything meaningful to do (e.g. Mafia's night phase, where only
        living mafia members act) -- without this, the runner would have to
        ask every agent, including dead ones and ones with no real choice
        to make, wasting an LLM call per tick for no effect. Turn-based
        phases don't need this hook: agent_iter() already controls exactly
        who acts each turn-based tick.
        """
        return None
