"""Agent interface -- the only thing the runner asks of any agent
implementation, LLM-backed or scripted."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..core.types import Action, Observation


class SimAgent(ABC):
    @abstractmethod
    def act(self, obs: Observation) -> Action:
        """Decide an action given only the agent's own observation -- never
        given access to ground truth. Implementations that need to call an
        LLM (see llm_agent.LLMSimAgent) build a prompt from `obs` alone."""
        ...
