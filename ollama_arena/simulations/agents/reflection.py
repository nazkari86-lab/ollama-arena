"""Periodic reflection (GPTeam-inspired): every N ticks, summarize an
agent's recent memory stream into a short higher-level insight, stored
back onto its BrainProfile so future prompts see the gist of what
happened instead of just the raw witnessed-event list.

Opt-in only -- see SimulationManager.start_run()'s `reflect_every`
parameter. Default off, so existing recorded traces stay byte-for-byte
reproducible unless a run explicitly enables this.
"""
from __future__ import annotations

from .profile import BrainProfile

_REFLECTION_NUM_PREDICT = 80


def generate_reflection(profile: BrainProfile, backend, model: str) -> str:
    """One LLM call summarizing `profile.recent_stream()` into a short
    insight. Returns "" if there's nothing in the stream yet -- callers
    should skip storing an empty reflection rather than overwrite a
    previous, more useful one with nothing."""
    stream = profile.recent_stream()
    if not stream:
        return ""
    lines = [f"  [{event.tick}] {event.kind}: {event.payload}" for event in stream]
    prompt = (
        f"You are agent {profile.agent_id}, reflecting on recent events.\n"
        "Recent events you witnessed:\n" + "\n".join(lines) + "\n\n"
        "In 1-2 short sentences, summarize the key insight or pattern from "
        "these events that would help you make better decisions going "
        "forward. Output ONLY the summary, no preamble."
    )
    result = backend.generate(model, prompt, num_predict=_REFLECTION_NUM_PREDICT)
    return result.text.strip()


def should_reflect(tick: int, reflect_every: int | None) -> bool:
    """True on every Nth tick (tick == N, 2N, 3N, ...). tick 0 never
    reflects -- there's nothing to summarize yet at the start of a run."""
    if not reflect_every or reflect_every <= 0:
        return False
    return tick > 0 and tick % reflect_every == 0
