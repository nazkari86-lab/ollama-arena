"""Pure functions for Sims-world money/needs transitions.

No hidden state, no side effects beyond the NPCStatus passed in, so the
daily-tick loop in scenarios/sims_world.py stays easy to reason about and
test -- every function here is independently unit-testable without a World.
"""
from __future__ import annotations

from .entities import NPCStatus

DAILY_DECAY = {"hunger": 15.0, "energy": 10.0, "social": 8.0, "mood": 5.0}
WORK_ENERGY_COST = 15.0
REST_ENERGY_GAIN = 35.0
SOCIALIZE_ENERGY_COST = 5.0
SOCIALIZE_SOCIAL_GAIN = 25.0
FOOD_HUNGER_GAIN = 40.0
CONFLICT_MOOD_COST = 20.0
RENT_DEBT_MOOD_PENALTY = 10.0

# Per-job wage. "baker" is pinned at the original flat WORK_WAGE value so
# the already-balanced work/spend/rest cycle exercised by
# test_balanced_agent_survives_the_full_day_budget keeps the same
# economics it was tuned against. Other jobs are new, real differentiation
# -- this replaces the old "every job pays the same flat 50" placeholder.
JOB_CATALOG = {
    "baker": 50.0,
    "barista": 35.0,
    "office_worker": 60.0,
    "shopkeeper": 45.0,
}
# Wage for an employed agent whose job string isn't in JOB_CATALOG --
# still better than nothing, but below every named job, since an
# unrecognized job has no negotiated/skilled rate.
DEFAULT_WAGE = 30.0

RENT_PER_DAY = 25.0

# Spend category -> (need restored, amount). "food" keeps its original
# FOOD_HUNGER_GAIN value/behavior; "leisure"/"healthcare" are new. An
# unrecognized category still spends money (matches the old food-only
# behavior's silent no-op for anything else) but restores nothing.
SPEND_EFFECTS = {
    "food": ("hunger", FOOD_HUNGER_GAIN),
    "leisure": ("mood", 30.0),
    "healthcare": ("energy", 25.0),
}


def apply_daily_decay(status: NPCStatus) -> None:
    for name, amount in DAILY_DECAY.items():
        status.needs[name] -= amount
    status.clamp_needs()


def apply_work(status: NPCStatus) -> float:
    """Returns the wage actually earned (0 if unemployed)."""
    if not status.job:
        return 0.0
    wage = JOB_CATALOG.get(status.job, DEFAULT_WAGE)
    status.money += wage
    status.needs["energy"] -= WORK_ENERGY_COST
    status.clamp_needs()
    return wage


def apply_rest(status: NPCStatus) -> None:
    status.needs["energy"] += REST_ENERGY_GAIN
    status.clamp_needs()


def apply_socialize(status: NPCStatus) -> None:
    status.needs["social"] += SOCIALIZE_SOCIAL_GAIN
    status.needs["energy"] -= SOCIALIZE_ENERGY_COST
    status.clamp_needs()


def apply_conflict(status: NPCStatus) -> None:
    status.needs["mood"] -= CONFLICT_MOOD_COST
    status.clamp_needs()


def apply_spend(status: NPCStatus, amount: float, on: str) -> bool:
    """Returns False (no-op, nothing deducted) if the agent can't afford
    it -- callers must never let money go negative."""
    if amount <= 0 or amount > status.money:
        return False
    status.money -= amount
    effect = SPEND_EFFECTS.get(on)
    if effect:
        need_name, gain = effect
        status.needs[need_name] += gain
    status.clamp_needs()
    return True


def apply_rent_bill(status: NPCStatus, rent: float = RENT_PER_DAY) -> bool:
    """Charge one day's rent. Returns True if paid from money, False if it
    went to debt instead.

    Deliberately doesn't drain money to zero on a shortfall (a fixed,
    sudden bankruptcy cliff isn't more "real" than the alternative, just
    less recoverable) -- an unaffordable bill accrues as debt and costs
    mood instead, leaving room for a future scenario rule (eviction,
    wage garnishment, etc.) to act on accumulated debt deliberately rather
    than this function silently deciding that policy on its own.
    """
    if status.money >= rent:
        status.money -= rent
        return True
    status.debt += rent
    status.needs["mood"] -= RENT_DEBT_MOOD_PENALTY
    status.clamp_needs()
    return False


def is_starving_to_death(status: NPCStatus) -> bool:
    return status.needs["hunger"] <= 0.0 or status.needs["energy"] <= 0.0
