"""Agent brain profile -- agentsociety-inspired Status+Stream split.

Status = persona/role/secret-allegiance/needs/money/job: static-ish
structured fields a scenario defines and reads directly (e.g. Mafia checks
`status["role"]`, Sims-world checks `status["money"]`). Stream = a capped,
time-ordered slice of events used to build LLM prompt context without
letting it grow unboundedly across a long run.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..core.types import AgentId, Event

DEFAULT_STREAM_CAP = 40


@dataclass
class BrainProfile:
    agent_id: AgentId
    persona: dict = field(default_factory=dict)
    status: dict = field(default_factory=dict)
    stream_cap: int = DEFAULT_STREAM_CAP
    _stream: list[Event] = field(default_factory=list, repr=False)

    def remember(self, event: Event) -> None:
        """Append to the stream, dropping the oldest entries once over cap.

        A hard cap (not a summarizer) is the deliberate choice here: an LLM
        prompt built from `recent_stream()` must have a bounded token cost
        regardless of how long the run has been going. Scenarios needing
        longer memory should fold older events into `status` themselves
        (e.g. a running relationship-affinity score) rather than relying on
        the raw stream growing.
        """
        self._stream.append(event)
        if len(self._stream) > self.stream_cap:
            self._stream = self._stream[-self.stream_cap:]

    def recent_stream(self) -> list[Event]:
        return list(self._stream)
