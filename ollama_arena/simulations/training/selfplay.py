"""Self-play orchestration -- intentionally stubbed in Phase 4.

The intended shape (Phase 5+): run N SimulationManager episodes of a
game-playing scenario using a trained imitation-learning checkpoint as one
of the agents, to iteratively improve it against itself. Not wired into
any CLI/web route yet -- raising NotImplementedError here is deliberate,
not a placeholder pretending to work.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SelfPlayConfig:
    n_episodes: int = 10
    scenario: str = "rps"


def run_self_play(config: SelfPlayConfig) -> None:
    raise NotImplementedError(
        "Self-play orchestration is a Phase 5+ feature, not yet implemented."
    )
