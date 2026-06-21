"""selfplay.py is an intentional Phase 5+ stub -- it must fail loudly
(NotImplementedError), never silently no-op or pretend to run."""
import pytest

from ollama_arena.simulations.training.selfplay import SelfPlayConfig, run_self_play


def test_run_self_play_raises_not_implemented():
    with pytest.raises(NotImplementedError, match="Phase 5"):
        run_self_play(SelfPlayConfig())


def test_self_play_config_has_sane_defaults():
    config = SelfPlayConfig()
    assert config.n_episodes > 0
    assert config.scenario
