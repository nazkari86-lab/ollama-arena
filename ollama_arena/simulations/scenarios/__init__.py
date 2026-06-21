"""Importing this package registers every built-in scenario.

core.scenario._ensure_builtin_scenarios_registered() imports this module to
populate the registry -- each submodule below calls register_scenario() at
import time, so adding scenario #N is "add one file, import it here."
"""
from __future__ import annotations

from . import educational, game_playing, mafia, rps, sandbox_universe, sims_world  # noqa: F401

__all__ = [
    "educational", "game_playing", "mafia", "rps", "sandbox_universe", "sims_world",
]
