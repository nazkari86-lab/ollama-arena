"""Validation boundary between raw LLM output and a structured `Action`.

An LLM-backed agent never gets to mutate world state directly -- it can only
*propose* an action as text/JSON, which must parse cleanly against the
scenario's `ActionSchema` before `World.step_*()` will accept it. This module
is the only place that boundary is crossed.

Deliberately stdlib-only (dataclasses, no pydantic): the simulations package
must be usable from the CLI without pulling in the `web` extra's dependency
tree, and these schemas are simple enough (a handful of str/int/float/bool/
Literal fields per action kind) that a small manual validator is enough.
"""
from __future__ import annotations

import dataclasses
import json
import re
import typing
from dataclasses import MISSING, dataclass, fields
from typing import Any, get_args, get_origin

from .types import Action, AgentId


@dataclass
class ActionSchema:
    """Base class for a scenario's per-action-kind payload schema.

    Concrete scenarios subclass this per action kind (e.g. `SpeakAction`,
    `VoteAction` for Mafia) as plain dataclasses with typed fields, and
    register the kind -> schema mapping via `ScenarioSpec.action_schema`
    (see core/scenario.py). Supported field types: str, int, float, bool,
    `Optional[...]` of those, and `Literal[...]` of str/int for enum-like
    choices.
    """


class ActionParseError(Exception):
    """Raised when raw LLM output cannot be parsed/validated into an Action.

    Carries the raw text and the underlying error so callers (typically
    `agents.llm_agent.LLMSimAgent`) can decide whether to retry with a
    corrective prompt or fall back to a no-op/forfeit action.
    """
    def __init__(self, raw_text: str, reason: str):
        super().__init__(reason)
        self.raw_text = raw_text
        self.reason = reason


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(raw_text: str) -> dict[str, Any]:
    """Pull the first JSON object out of raw LLM text.

    Models routinely wrap JSON in prose or markdown code fences even when
    explicitly asked for bare JSON -- this tries a direct parse first, then
    falls back to extracting the first {...} block, rather than failing on
    every minor formatting deviation.
    """
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass
    match = _JSON_BLOCK_RE.search(raw_text)
    if not match:
        raise ActionParseError(raw_text, "no JSON object found in output")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise ActionParseError(raw_text, f"invalid JSON: {e}") from e


def _check_type(value: Any, expected: Any) -> bool:
    origin = get_origin(expected)
    if origin is typing.Union:  # Optional[X] == Union[X, None]
        return any(_check_type(value, a) for a in get_args(expected))
    if origin is typing.Literal:
        return value in get_args(expected)
    if expected is float:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected is bool:
        return isinstance(value, bool)
    if expected is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if expected is str:
        return isinstance(value, str)
    if expected is type(None):
        return value is None
    return isinstance(value, expected) if isinstance(expected, type) else True


def validate_schema(schema_cls: type[ActionSchema], data: dict[str, Any]) -> ActionSchema:
    """Build + type-check a schema_cls instance from a raw dict.

    Raises ValueError (not ActionParseError -- this is a lower-level helper
    also useful for tests) on a missing required field or a type mismatch.
    """
    # Field annotations are unresolved strings whenever the schema's defining
    # module has `from __future__ import annotations` (every module in this
    # codebase does) -- get_type_hints() resolves them against that module's
    # globals so _check_type() sees real type objects, not "str"/"int" text.
    hints = typing.get_type_hints(schema_cls)
    kwargs: dict[str, Any] = {}
    for f in fields(schema_cls):
        expected = hints.get(f.name, f.type)
        if f.name not in data:
            if f.default is MISSING and f.default_factory is MISSING:  # type: ignore[misc]
                raise ValueError(f"missing required field {f.name!r}")
            continue
        value = data[f.name]
        if not _check_type(value, expected):
            raise ValueError(f"field {f.name!r} expected {expected}, got {type(value).__name__}")
        kwargs[f.name] = value
    return schema_cls(**kwargs)


def action_schema_examples(
    schema_by_kind: dict[str, type[ActionSchema]],
) -> list[str]:
    """Return compact, valid JSON examples suitable for an LLM prompt."""
    examples = []
    for kind, schema_cls in sorted(schema_by_kind.items()):
        hints = typing.get_type_hints(schema_cls)
        data: dict[str, Any] = {"kind": kind}
        for field_def in fields(schema_cls):
            annotation = hints.get(field_def.name, field_def.type)
            origin = get_origin(annotation)
            args = get_args(annotation)
            if origin is typing.Literal:
                value = args[0]
            elif field_def.default is not MISSING:
                value = field_def.default
            elif annotation is str:
                value = f"<{field_def.name}>"
            elif annotation is bool:
                value = False
            elif annotation is int:
                value = 0
            elif annotation is float:
                value = 0.0
            else:
                non_null = [arg for arg in args if arg is not type(None)]
                value = None if not non_null else f"<{field_def.name}>"
            data[field_def.name] = value
        examples.append(json.dumps(data, separators=(",", ":")))
    return examples


def parse_action(
    raw_text: str,
    agent_id: AgentId,
    schema_by_kind: dict[str, type[ActionSchema]],
) -> Action:
    """Parse + validate raw LLM output into a structured `Action`.

    `schema_by_kind` maps an action "kind" string (read from the parsed
    JSON's "kind" field) to the schema that kind's payload must satisfy --
    this lets a single scenario expose several action kinds (e.g. Mafia's
    speak/vote/night_action) without one giant schema that has to
    special-case which fields apply when.

    Raises ActionParseError on any failure; never silently coerces invalid
    input into a "best guess" action.
    """
    data = _extract_json(raw_text)
    kind = data.get("kind")
    if kind not in schema_by_kind:
        raise ActionParseError(
            raw_text,
            f"unknown or missing action kind {kind!r}; expected one of {sorted(schema_by_kind)}",
        )
    schema_cls = schema_by_kind[kind]
    raw_payload = {k: v for k, v in data.items() if k != "kind"}
    try:
        validated = validate_schema(schema_cls, raw_payload)
    except ValueError as e:
        raise ActionParseError(raw_text, str(e)) from e
    # Read the payload back off the validated instance, not raw_payload --
    # a field the LLM omitted but the schema defaults (e.g. confidence:
    # float = 1.0) must appear in Action.payload with that default applied,
    # not be silently absent just because the model never mentioned it.
    payload = {f.name: getattr(validated, f.name) for f in dataclasses.fields(schema_cls)}
    return Action(agent_id=agent_id, kind=kind, payload=payload, raw_llm_output=raw_text)
