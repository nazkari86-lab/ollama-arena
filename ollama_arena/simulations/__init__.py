"""LLM-agent-driven simulations subsystem for ollama-arena.

Additive on top of the existing arena/match/tournament/ELO stack: agents
backed by local models act inside rule-governed worlds (social deduction,
life simulation, sandbox universes, ...), proposing actions that the engine
validates and applies. See ollama_arena/simulations/core/ for the engine
contract shared by every scenario.
"""
from __future__ import annotations

from .core.scenario import register_scenario, get_scenario, list_scenarios
from .core.runner import SimulationManager

__all__ = [
    "SimulationManager",
    "register_scenario",
    "get_scenario",
    "list_scenarios",
]
