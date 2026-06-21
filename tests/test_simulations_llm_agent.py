"""LLMSimAgent: prompt construction never leaks ground truth, parse-failure
retry-once-then-forfeit behavior, and PerfTracker recording."""
from unittest.mock import MagicMock

from ollama_arena.backends.base import GenResult
from ollama_arena.simulations.agents.llm_agent import FORFEIT_KIND, LLMSimAgent
from ollama_arena.simulations.core.types import Event, Observation, WITNESS_ALL
from ollama_arena.simulations.scenarios.rps import RPSAction

SCHEMAS = {"choose": RPSAction}


def _mock_backend(*texts):
    backend = MagicMock()
    backend.name = "mock"
    backend.generate.side_effect = [GenResult(text=t, model="x") for t in texts]
    return backend


def test_first_try_valid_json_returns_immediately():
    backend = _mock_backend('{"kind": "choose", "choice": "rock"}')
    agent = LLMSimAgent("a", "fake-model", SCHEMAS, backend=backend)
    obs = Observation(agent_id="a", tick=0, visible_events=())
    action = agent.act(obs)
    assert action.kind == "choose"
    assert action.payload == {"choice": "rock"}
    assert backend.generate.call_count == 1


def test_retries_once_on_parse_failure_then_succeeds():
    backend = _mock_backend("not json at all", '{"kind": "choose", "choice": "paper"}')
    agent = LLMSimAgent("a", "fake-model", SCHEMAS, backend=backend)
    obs = Observation(agent_id="a", tick=0, visible_events=())
    action = agent.act(obs)
    assert action.payload == {"choice": "paper"}
    assert backend.generate.call_count == 2
    # the retry prompt must reference the original failure reason
    retry_prompt = backend.generate.call_args_list[1].args[1]
    assert "no JSON object found" in retry_prompt


def test_forfeits_after_two_consecutive_parse_failures():
    backend = _mock_backend("garbage", "still garbage")
    agent = LLMSimAgent("b", "fake-model", SCHEMAS, backend=backend)
    obs = Observation(agent_id="b", tick=0, visible_events=())
    action = agent.act(obs)
    assert action.kind == FORFEIT_KIND
    assert action.agent_id == "b"
    assert backend.generate.call_count == 2


def test_build_prompt_only_uses_observation_and_profile_never_ground_truth():
    """The prompt-builder must have no way to leak ground truth -- it is
    constructed from obs.visible_events + the agent's own profile only.
    This test asserts a private/unwitnessed event never appears even if it
    somehow ended up in the agent's own profile.stream (defense in depth:
    the real guarantee comes from World.observe() never including it in
    `obs` in the first place, but the prompt-builder must not reach past
    `obs` to find it either)."""
    backend = _mock_backend('{"kind": "choose", "choice": "rock"}')
    agent = LLMSimAgent(
        "a", "fake-model", SCHEMAS, backend=backend,
        config={"persona": {"name": "Alice"}, "status": {"score": 2}},
    )
    visible = (Event(id="e1", tick=0, kind="round_result", payload={"outcome": "a"}, witness_ids=WITNESS_ALL),)
    obs = Observation(agent_id="a", tick=1, visible_events=visible, status={"score": 2})
    prompt = agent.build_prompt(obs)
    assert "Alice" in prompt
    assert "round_result" in prompt
    assert "score" in prompt
    assert '{"kind":"choose","choice":"rock"}' in prompt
    # No ground-truth/world-state accessor exists on the agent at all
    assert not hasattr(agent, "state")


def test_build_prompt_renders_strategy_hint_once_not_duplicated_in_status():
    # "strategy_hint" is a generic, scenario-agnostic display hint (Mafia
    # sets one per role; see scenarios/mafia.py) -- this agent must render
    # it as its own line and pop it out of status, mirroring how
    # "valid_kinds" is already handled, so it isn't shown twice.
    backend = _mock_backend('{"kind": "choose", "choice": "rock"}')
    agent = LLMSimAgent("a", "fake-model", SCHEMAS, backend=backend)
    obs = Observation(
        agent_id="a", tick=0, visible_events=(),
        status={"role": "mafia", "strategy_hint": "Keep your story consistent."},
    )
    prompt = agent.build_prompt(obs)
    assert "Strategy: Keep your story consistent." in prompt
    assert prompt.count("Keep your story consistent.") == 1


def test_perf_tracker_records_one_call_per_generate():
    backend = _mock_backend('{"kind": "choose", "choice": "rock"}')
    perf = MagicMock()
    agent = LLMSimAgent("a", "fake-model", SCHEMAS, backend=backend, perf_tracker=perf)
    obs = Observation(agent_id="a", tick=0, visible_events=())
    agent.act(obs)
    assert perf.record.call_count == 1
    args = perf.record.call_args.args
    assert args[0] == "fake-model"


def test_perf_tracker_not_required():
    backend = _mock_backend('{"kind": "choose", "choice": "rock"}')
    agent = LLMSimAgent("a", "fake-model", SCHEMAS, backend=backend)
    obs = Observation(agent_id="a", tick=0, visible_events=())
    action = agent.act(obs)  # must not raise even with perf_tracker=None
    assert action.kind == "choose"


def test_generate_called_with_bounded_num_predict_and_num_ctx():
    # Regression: act() called backend.generate(model, prompt) with NO
    # opts at all, so every per-tick decision -- a one-line JSON action --
    # inherited OllamaBackend's num_predict=16384/num_ctx=65536 defaults
    # meant for full Arena-battle answers. Combined with
    # OLLAMA_MAX_LOADED_MODELS=1 forcing a full model reload on every turn
    # a scenario alternates between two different agent models, the
    # oversized num_ctx made every single reload's KV-cache allocation
    # dramatically more expensive than it needed to be (measured: a cold
    # qwen3:8b reload went from ~48s at num_ctx=65536 down to ~5s at
    # num_ctx=4096 against a short sim prompt on real hardware) -- this is
    # the actual reason multi-agent simulations appeared to hang/never
    # finish. A short per-tick JSON decision needs neither.
    backend = _mock_backend('{"kind": "choose", "choice": "rock"}')
    agent = LLMSimAgent("a", "fake-model", SCHEMAS, backend=backend)
    obs = Observation(agent_id="a", tick=0, visible_events=())
    agent.act(obs)
    kwargs = backend.generate.call_args_list[0].kwargs
    assert 0 < kwargs["num_predict"] <= 2000
    assert 0 < kwargs["num_ctx"] <= 16384


def test_num_ctx_scales_with_prompt_length_but_stays_bounded():
    # A long event history (many rounds of Mafia/Sims-world) must not be
    # silently truncated by an undersized fixed num_ctx, but must also
    # never regress to the old unbounded 65536 default.
    backend = _mock_backend('{"kind": "choose", "choice": "rock"}')
    agent = LLMSimAgent("a", "fake-model", SCHEMAS, backend=backend)
    long_events = tuple(
        Event(id=f"e{i}", tick=i, kind="speak", payload={"text": "x" * 200}, witness_ids=WITNESS_ALL)
        for i in range(80)
    )
    obs = Observation(agent_id="a", tick=80, visible_events=long_events)
    agent.act(obs)
    kwargs = backend.generate.call_args_list[0].kwargs
    short_backend = _mock_backend('{"kind": "choose", "choice": "rock"}')
    short_agent = LLMSimAgent("a", "fake-model", SCHEMAS, backend=short_backend)
    short_agent.act(Observation(agent_id="a", tick=0, visible_events=()))
    short_kwargs = short_backend.generate.call_args_list[0].kwargs
    assert kwargs["num_ctx"] > short_kwargs["num_ctx"]
    assert kwargs["num_ctx"] <= 16384
