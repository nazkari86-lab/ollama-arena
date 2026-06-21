"""Per-scenario scoring -- each scenario supplies one ScenarioScorer via its
ScenarioSpec.scorer_factory; the runner calls it once an episode ends."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..core.types import EpisodeResult


class ScenarioScorer(ABC):
    @abstractmethod
    def score(self, episode: EpisodeResult) -> dict[str, float]:
        """Return named metrics for a completed/truncated episode (e.g.
        {"winner_is_town": 1.0, "ticks_to_resolution": 14.0})."""
        ...
