"""reflection.py: opt-in periodic memory-stream summarization."""
from unittest.mock import MagicMock

from ollama_arena.backends.base import GenResult
from ollama_arena.simulations.agents.profile import BrainProfile
from ollama_arena.simulations.agents.reflection import generate_reflection, should_reflect
from ollama_arena.simulations.core.types import Event, WITNESS_ALL


def _event(tick, kind="said", payload=None):
    return Event(id=f"e{tick}", tick=tick, kind=kind, payload=payload or {}, witness_ids=WITNESS_ALL)


class TestShouldReflect:
    def test_false_when_reflect_every_is_none(self):
        assert should_reflect(10, None) is False

    def test_false_when_reflect_every_is_zero(self):
        assert should_reflect(10, 0) is False

    def test_false_on_tick_zero_even_if_divisible(self):
        assert should_reflect(0, 5) is False

    def test_true_on_exact_multiples(self):
        assert should_reflect(5, 5) is True
        assert should_reflect(10, 5) is True
        assert should_reflect(15, 5) is True

    def test_false_on_non_multiples(self):
        assert should_reflect(4, 5) is False
        assert should_reflect(6, 5) is False


class TestGenerateReflection:
    def test_empty_stream_returns_empty_string_no_backend_call(self):
        profile = BrainProfile(agent_id="a")
        backend = MagicMock()
        result = generate_reflection(profile, backend, "fake-model")
        assert result == ""
        backend.generate.assert_not_called()

    def test_summarizes_stream_via_one_backend_call(self):
        profile = BrainProfile(agent_id="a")
        profile.remember(_event(1, "said", {"text": "hello"}))
        profile.remember(_event(2, "moved", {"to": "kitchen"}))
        backend = MagicMock()
        backend.generate.return_value = GenResult(text="Agent a tends to socialize then relocate.", model="x")
        result = generate_reflection(profile, backend, "fake-model")
        assert result == "Agent a tends to socialize then relocate."
        assert backend.generate.call_count == 1
        prompt = backend.generate.call_args.args[1]
        assert "said" in prompt
        assert "moved" in prompt

    def test_strips_whitespace_from_backend_output(self):
        profile = BrainProfile(agent_id="a")
        profile.remember(_event(1))
        backend = MagicMock()
        backend.generate.return_value = GenResult(text="  padded insight  \n", model="x")
        result = generate_reflection(profile, backend, "fake-model")
        assert result == "padded insight"
