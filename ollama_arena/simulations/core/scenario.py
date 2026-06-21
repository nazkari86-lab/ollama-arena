"""Scenario registry -- the mechanism for adding new simulation types
without touching the core engine.

Each scenario module (scenarios/rps.py, scenarios/mafia.py, ...) builds one
`ScenarioSpec` and calls `register_scenario()` at import time. The runner and
CLI/web layers only ever go through `get_scenario()`/`list_scenarios()`, so
adding scenario #6 means adding one new file, not editing this one.
"""
from __future__ import annotations

import dataclasses
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable

from .action_schema import ActionSchema
from .types import StepMode
from .world import World


@dataclass
class ScenarioSpec:
    name: str
    description: str
    world_factory: Callable[..., World]
    action_schema_by_kind: dict[str, type[ActionSchema]]
    step_mode_by_phase: dict[str, StepMode] = field(default_factory=dict)
    default_config: dict[str, Any] = field(default_factory=dict)
    scorer_factory: Callable[[], Any] | None = None


_REGISTRY: dict[str, ScenarioSpec] = {}


def register_scenario(spec: ScenarioSpec) -> None:
    if spec.name in _REGISTRY:
        raise ValueError(f"scenario {spec.name!r} is already registered")
    for kind, schema_cls in spec.action_schema_by_kind.items():
        # A schema class that subclasses ActionSchema but forgets its own
        # @dataclass decorator silently has zero fields (dataclass-ness
        # isn't inherited) -- validate_schema() would then accept any
        # payload for that kind without checking anything. Catch that here,
        # at registration time, instead of letting it fail open at runtime.
        # inspect.get_annotations() (not __dict__["__annotations__"]) is
        # required for this to work under PEP 649 lazy annotations
        # (Python 3.14+), where a class's own annotations aren't eagerly
        # materialized into __dict__.
        declared = set(inspect.get_annotations(schema_cls))
        actual = {f.name for f in dataclasses.fields(schema_cls)} if dataclasses.is_dataclass(schema_cls) else set()
        if declared and not declared.issubset(actual):
            raise TypeError(
                f"scenario {spec.name!r} action kind {kind!r}: schema class "
                f"{schema_cls.__name__} declares fields {sorted(declared)} but is "
                f"missing a @dataclass decorator (fields(): {sorted(actual)})"
            )
    _REGISTRY[spec.name] = spec


def get_scenario(name: str) -> ScenarioSpec:
    _ensure_builtin_scenarios_registered()
    if name not in _REGISTRY:
        raise KeyError(f"unknown scenario {name!r}; available: {sorted(_REGISTRY)}")
    return _REGISTRY[name]


def list_scenarios() -> list[ScenarioSpec]:
    _ensure_builtin_scenarios_registered()
    return list(_REGISTRY.values())


def _ensure_builtin_scenarios_registered() -> None:
    """Import scenarios/ so each module's register_scenario() call runs.

    Importing `simulations.scenarios` is what triggers registration -- the
    registry is otherwise empty even though this module is imported, since
    `core/` deliberately doesn't import `scenarios/` at module load time
    (that would invert the intended dependency direction: scenarios depend
    on core, not the other way around). Callers that need the registry
    populated (the runner, CLI, web routes) call this first.
    """
    from .. import scenarios  # noqa: F401
