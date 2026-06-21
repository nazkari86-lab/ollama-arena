"""Validation boundary between raw LLM output and a structured Action."""
from dataclasses import dataclass
from typing import Literal

import pytest

from ollama_arena.simulations.core.action_schema import (
    ActionParseError, ActionSchema, parse_action, validate_schema,
)


@dataclass
class _VoteAction(ActionSchema):
    target: str
    confidence: float = 1.0


@dataclass
class _ChoiceAction(ActionSchema):
    choice: Literal["rock", "paper", "scissors"]


SCHEMAS = {"vote": _VoteAction, "choose": _ChoiceAction}


def test_parses_bare_json():
    action = parse_action('{"kind": "vote", "target": "agent_b"}', "agent_a", SCHEMAS)
    assert action.kind == "vote"
    assert action.payload == {"target": "agent_b", "confidence": 1.0}
    assert action.agent_id == "agent_a"


def test_extracts_json_wrapped_in_prose():
    """Models routinely wrap JSON in explanatory text even when told not
    to -- this must still parse instead of failing on every minor
    formatting deviation."""
    raw = 'Sure, I will vote now: {"kind": "vote", "target": "agent_c"} -- done.'
    action = parse_action(raw, "agent_a", SCHEMAS)
    assert action.payload["target"] == "agent_c"


def test_rejects_unknown_kind():
    with pytest.raises(ActionParseError, match="unknown or missing action kind"):
        parse_action('{"kind": "nope"}', "agent_a", SCHEMAS)


def test_rejects_missing_kind_field():
    with pytest.raises(ActionParseError, match="unknown or missing action kind"):
        parse_action('{"target": "agent_b"}', "agent_a", SCHEMAS)


def test_rejects_missing_required_field():
    with pytest.raises(ActionParseError, match="missing required field"):
        parse_action('{"kind": "vote"}', "agent_a", SCHEMAS)


def test_rejects_non_json_text():
    with pytest.raises(ActionParseError, match="no JSON object found"):
        parse_action("I think I'll vote for agent_b.", "agent_a", SCHEMAS)


def test_rejects_value_outside_literal_choices():
    """Regression guard: an earlier version of _check_type didn't resolve
    `from __future__ import annotations`-deferred string type hints, so a
    Literal["rock","paper","scissors"] field silently accepted any string
    (including "lizard") without ever checking membership."""
    with pytest.raises(ActionParseError, match="expected"):
        parse_action('{"kind": "choose", "choice": "lizard"}', "a", SCHEMAS)


def test_rejects_wrong_type_for_float_field():
    with pytest.raises(ActionParseError, match="expected"):
        parse_action('{"kind": "vote", "target": "x", "confidence": "high"}', "a", SCHEMAS)


def test_accepts_int_for_float_field():
    """bool must not be accepted where float is expected (bool is an int
    subclass in Python) but a plain int must be."""
    action = parse_action('{"kind": "vote", "target": "x", "confidence": 1}', "a", SCHEMAS)
    assert action.payload["confidence"] == 1


def test_rejects_bool_for_float_field():
    with pytest.raises(ActionParseError, match="expected"):
        parse_action('{"kind": "vote", "target": "x", "confidence": true}', "a", SCHEMAS)


def test_default_field_not_required():
    action = parse_action('{"kind": "vote", "target": "agent_b"}', "a", SCHEMAS)
    assert action.payload["confidence"] == 1.0


def test_raw_llm_output_preserved_verbatim():
    raw = '{"kind": "vote", "target": "agent_b"}'
    action = parse_action(raw, "a", SCHEMAS)
    assert action.raw_llm_output == raw


def test_validate_schema_raises_value_error_directly():
    """validate_schema() is also used standalone (not just via parse_action)
    -- it must raise plain ValueError, not the higher-level ActionParseError."""
    with pytest.raises(ValueError):
        validate_schema(_VoteAction, {})
