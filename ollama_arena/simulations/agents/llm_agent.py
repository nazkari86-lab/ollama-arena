"""LLMSimAgent -- wraps a local-model Backend as a SimAgent.

An in-sim LLM call is exactly the same kind of call the rest of the arena
already makes, so this reuses `backends.Backend`/`GenResult` directly rather
than inventing a parallel "sim model client." A scenario's per-agent prompt
is built from the agent's `Observation` + `BrainProfile` only -- never from
`World.state()` -- and the raw text response is run through
`action_schema.parse_action()`, with one retry on a parse failure before
falling back to a forfeit/no-op action.
"""
from __future__ import annotations

import logging
from typing import Any

from ..core.action_schema import (
    ActionParseError,
    ActionSchema,
    action_schema_examples,
    parse_action,
)
from ..core.types import Action, AgentId, Observation
from .base import SimAgent
from .profile import BrainProfile

log = logging.getLogger("arena.simulations.agents")

FORFEIT_KIND = "forfeit"

# A sim turn is a one-line JSON action decision, not a full Arena-battle
# answer -- it must NOT inherit OllamaBackend's num_predict=16384/
# num_ctx=65536 defaults. Those defaults made every per-tick reload (any
# scenario alternating between 2+ different agent models forces a full
# reload every turn under OLLAMA_MAX_LOADED_MODELS=1) far more expensive
# than necessary -- measured on real hardware: a cold qwen3:8b reload
# dropped from ~48s at num_ctx=65536 to ~5s at num_ctx=4096 for the same
# short prompt. This was the actual reason multi-agent simulations
# appeared to hang/never finish.
_NUM_PREDICT = 600          # brief reasoning + a short JSON object
_MIN_NUM_CTX = 2048
_MAX_NUM_CTX = 16384


def _estimate_num_ctx(prompt: str) -> int:
    """Size num_ctx off the actual prompt instead of a blind constant.

    Scenarios like Mafia/Sims-world accumulate every witnessed event into
    every future prompt (see World.observe()) with no history cap, so a
    fixed small num_ctx would silently truncate old-but-relevant context
    on a long-running run. ~3 chars/token is a deliberately conservative
    (oversized) estimate -- under-counting truncates context silently,
    over-counting just costs a slightly bigger KV-cache allocation.
    """
    est_tokens = len(prompt) // 3 + _NUM_PREDICT
    return max(_MIN_NUM_CTX, min(_MAX_NUM_CTX, est_tokens))


class LLMSimAgent(SimAgent):
    def __init__(
        self,
        agent_id: AgentId,
        model: str,
        action_schema_by_kind: dict[str, type[ActionSchema]],
        config: dict[str, Any] | None = None,
        backend=None,
        ollama_url: str = "http://localhost:11434",
        perf_tracker=None,
    ):
        self.agent_id = agent_id
        self.model = model
        self.action_schema_by_kind = action_schema_by_kind
        self.config = config or {}
        self.profile = BrainProfile(
            agent_id=agent_id,
            persona=self.config.get("persona", {}),
            status=dict(self.config.get("status", {})),
        )
        if backend is None:
            from ...backends.auto import auto_backend
            backend = auto_backend(ollama_url)
        self._backend = backend
        self._perf = perf_tracker

    def build_prompt(self, obs: Observation) -> str:
        """Render the observation + brain profile into a model prompt.

        Deliberately does not take `World.state()` as an argument -- there
        is nothing here that *could* leak ground truth, since the only
        inputs are the witness-filtered `obs.visible_events` and this
        agent's own profile.
        """
        lines = [
            f"You are agent {self.agent_id}.",
        ]
        if self.profile.persona:
            lines.append(f"Persona: {self.profile.persona}")
        # "valid_kinds" is a display-only hint a scenario can set in
        # obs.status to narrow which action kinds make sense *this phase*
        # (e.g. Mafia only wants "vote" during its vote phase, not "speak")
        # -- pulled out of the dict before printing status so it isn't
        # shown twice (once here, once in the "Valid kind values" line).
        status = dict(obs.status)
        phase_valid_kinds = status.pop("valid_kinds", None)
        # "strategy_hint" is the same kind of optional, scenario-agnostic
        # display hint -- any scenario may set it in obs.status to give
        # role-specific strategic framing (Mafia sets one per role; see
        # scenarios/mafia.py) without this generic agent knowing anything
        # about Mafia roles specifically.
        strategy_hint = status.pop("strategy_hint", None)
        if strategy_hint:
            lines.append(f"Strategy: {strategy_hint}")
        if status:
            lines.append(f"Your current status: {status}")
        lines.append(f"Tick {obs.tick}. Recent events you witnessed:")
        for event in obs.visible_events:
            lines.append(f"  [{event.tick}] {event.kind}: {event.payload}")
        kinds = sorted(phase_valid_kinds) if phase_valid_kinds else sorted(self.action_schema_by_kind)
        active_schemas = {
            kind: self.action_schema_by_kind[kind]
            for kind in kinds
            if kind in self.action_schema_by_kind
        }
        lines.append(
            "Respond with ONLY a single JSON object describing your action. "
            f"Valid \"kind\" values: {kinds}."
        )
        lines.append("Valid JSON shapes (replace placeholder values):")
        lines.extend(f"  {example}" for example in action_schema_examples(active_schemas))
        return "\n".join(lines)

    def act(self, obs: Observation) -> Action:
        prompt = self.build_prompt(obs)
        result = self._backend.generate(
            self.model, prompt,
            num_predict=_NUM_PREDICT, num_ctx=_estimate_num_ctx(prompt),
        )
        if self._perf is not None:
            self._perf.record(
                self.model, getattr(self._backend, "name", "unknown"),
                result.tokens_in, result.tokens_out, result.latency_s, result.tps,
                result.time_to_first, category="simulation",
            )
        try:
            return parse_action(result.text, self.agent_id, self.action_schema_by_kind)
        except ActionParseError as e:
            # `e` is unbound again once this except block exits (Python
            # implicitly clears exception-handler variables on block exit),
            # so the failure reason must be saved to a plain local first.
            reason = e.reason
            log.warning(f"agent {self.agent_id} produced unparseable action; retrying once: {reason}")
        retry_prompt = (
            prompt + "\n\nYour previous response was invalid JSON or didn't match "
            f"the schema: {reason}. Respond again with ONLY a valid JSON object."
        )
        retry_result = self._backend.generate(
            self.model, retry_prompt,
            num_predict=_NUM_PREDICT, num_ctx=_estimate_num_ctx(retry_prompt),
        )
        try:
            return parse_action(retry_result.text, self.agent_id, self.action_schema_by_kind)
        except ActionParseError as e2:
            log.warning(f"agent {self.agent_id} failed twice; forfeiting this turn: {e2.reason}")
            return Action(
                agent_id=self.agent_id, kind=FORFEIT_KIND,
                payload={"reason": e2.reason}, raw_llm_output=retry_result.text,
            )
