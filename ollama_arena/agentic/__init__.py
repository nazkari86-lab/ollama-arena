"""Deep Agentic Evaluation system for ollama-arena v3.0.0.

This package provides advanced multi-agent evaluation capabilities including:
- Stateful VM Sandboxes for isolated task execution
- Swarm Battles for team-based agent competitions
- Red Teaming Arena for security evaluation
- Long-horizon task support for multi-hour evaluations
"""

from .sandbox import SandboxManager, SandboxConfig, SandboxResult
from .swarm import SwarmBattle, SwarmTeam, SwarmAgent, SwarmResult
from .redteam import RedTeamArena, RedTeamConfig, RedTeamResult

__all__ = [
    "SandboxManager",
    "SandboxConfig",
    "SandboxResult",
    "SwarmBattle",
    "SwarmTeam",
    "SwarmAgent",
    "SwarmResult",
    "RedTeamArena",
    "RedTeamConfig",
    "RedTeamResult",
]
