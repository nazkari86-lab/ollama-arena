"""Replay a stored run's event log -- for CLI `sim replay` and the
dashboard's replay scrubber. Reads from sim.db's sim_events table via
SimStore; never reconstructs a live World (replay is read-only inspection
of what already happened, not re-simulation)."""
from __future__ import annotations

from ..core.types import Event
from ..storage import SimStore


class ReplayPlayer:
    def __init__(self, run_id: str, db_path: str = "sim.db", witness_id: str | None = None):
        """`witness_id` replays only what one specific agent saw (filtered
        through Event.witness_ids), instead of the full ground-truth log --
        useful for auditing "did agent X ever see the private event Y."
        """
        self.run_id = run_id
        self.store = SimStore(db_path)
        self._events = self.store.get_events(run_id, witness_id=witness_id)
        self._pos = 0

    def __len__(self) -> int:
        return len(self._events)

    def reset(self) -> None:
        self._pos = 0

    def step(self) -> Event | None:
        if self._pos >= len(self._events):
            return None
        event = self._events[self._pos]
        self._pos += 1
        return event

    def seek(self, tick: int) -> list[Event]:
        """Jump to the start of `tick`, returning every event up to and
        including it (for a dashboard scrubber that wants the cumulative
        state at a point in the timeline, not just one event)."""
        seen = [e for e in self._events if e.tick <= tick]
        self._pos = len(seen)
        return seen

    def all_events(self) -> list[Event]:
        return list(self._events)
