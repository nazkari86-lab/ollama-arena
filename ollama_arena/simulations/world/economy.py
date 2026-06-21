"""Pure functions for Sims-world money/needs transitions.

No hidden state, no side effects beyond the NPCStatus passed in, so the
daily-tick loop in scenarios/sims_world.py stays easy to reason about and
test -- every function here is independently unit-testable without a World.
"""
from __future__ import annotations

from .entities import NPCStatus

DAILY_DECAY = {"hunger": 15.0, "energy": 10.0, "social": 8.0}
WORK_WAGE = 50.0
WORK_ENERGY_COST = 15.0
REST_ENERGY_GAIN = 35.0
SOCIALIZE_ENERGY_COST = 5.0
SOCIALIZE_SOCIAL_GAIN = 25.0
FOOD_HUNGER_GAIN = 40.0


def apply_daily_decay(status: NPCStatus) -> None:
    for name, amount in DAILY_DECAY.items():
        status.needs[name] -= amount
    status.clamp_needs()


def apply_work(status: NPCStatus) -> float:
    """Returns the wage actually earned (0 if unemployed)."""
    if not status.job:
        return 0.0
    status.money += WORK_WAGE
    status.needs["energy"] -= WORK_ENERGY_COST
    status.clamp_needs()
    return WORK_WAGE


def apply_rest(status: NPCStatus) -> None:
    status.needs["energy"] += REST_ENERGY_GAIN
    status.clamp_needs()


def apply_socialize(status: NPCStatus) -> None:
    status.needs["social"] += SOCIALIZE_SOCIAL_GAIN
    status.needs["energy"] -= SOCIALIZE_ENERGY_COST
    status.clamp_needs()


def apply_spend(status: NPCStatus, amount: float, on: str) -> bool:
    """Returns False (no-op, nothing deducted) if the agent can't afford
    it -- callers must never let money go negative."""
    if amount <= 0 or amount > status.money:
        return False
    status.money -= amount
    if on == "food":
        status.needs["hunger"] += FOOD_HUNGER_GAIN
    status.clamp_needs()
    return True


def is_starving_to_death(status: NPCStatus) -> bool:
    return status.needs["hunger"] <= 0.0 or status.needs["energy"] <= 0.0
