"""Sims-world entity models -- NPC status (needs/money/job) and homes.

Plain dataclasses, not World subclasses -- SimsWorldWorld owns the actual
simulation loop and persists these via to_dict()/from_dict() round-trips
through World.state()/restore_state().
"""
from __future__ import annotations

from dataclasses import dataclass, field

NEED_NAMES = ("hunger", "energy", "social")
NEED_MAX = 100.0
NEED_MIN = 0.0
NEED_START = 80.0


@dataclass
class Home:
    home_id: str
    owner_id: str


@dataclass
class NPCStatus:
    agent_id: str
    needs: dict[str, float] = field(default_factory=lambda: {n: NEED_START for n in NEED_NAMES})
    money: float = 50.0
    job: str | None = None
    home_id: str | None = None

    def clamp_needs(self) -> None:
        for name in NEED_NAMES:
            self.needs[name] = max(NEED_MIN, min(NEED_MAX, self.needs.get(name, 0.0)))

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id, "needs": dict(self.needs),
            "money": self.money, "job": self.job, "home_id": self.home_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NPCStatus":
        return cls(
            agent_id=data["agent_id"], needs=dict(data["needs"]),
            money=data["money"], job=data.get("job"), home_id=data.get("home_id"),
        )
