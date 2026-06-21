"""Affinity graph between agents, updated from socialize() actions.

Like everything else in this engine, the full graph is ground truth --
only ever exposed through `World.observe()` as the *requesting* agent's own
edges via `edges_for()`, never the complete graph. The complete graph stays
reachable only via `World.state()`, reserved for the engine/eval/replay.
"""
from __future__ import annotations


class RelationshipGraph:
    def __init__(self):
        self._affinity: dict[tuple[str, str], float] = {}

    @staticmethod
    def _key(a: str, b: str) -> tuple[str, str]:
        return (a, b) if a <= b else (b, a)

    def bump(self, a: str, b: str, delta: float) -> None:
        key = self._key(a, b)
        self._affinity[key] = self._affinity.get(key, 0.0) + delta

    def get(self, a: str, b: str) -> float:
        return self._affinity.get(self._key(a, b), 0.0)

    def edges_for(self, agent_id: str) -> dict[str, float]:
        """Only this agent's own relationships -- the observe()-safe view."""
        out: dict[str, float] = {}
        for (a, b), value in self._affinity.items():
            if a == agent_id:
                out[b] = value
            elif b == agent_id:
                out[a] = value
        return out

    def to_dict(self) -> dict:
        return {f"{a}|{b}": v for (a, b), v in self._affinity.items()}

    @classmethod
    def from_dict(cls, data: dict) -> "RelationshipGraph":
        graph = cls()
        for key, value in data.items():
            a, b = key.split("|", 1)
            graph._affinity[(a, b)] = value
        return graph
