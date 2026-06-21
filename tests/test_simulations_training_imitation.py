"""imitation.py: the supervised training loop, run for real on a tiny
synthetic dataset (CPU, deterministic, no real model download or Ollama
connection needed). Requires the [finetune] extra (torch) -- collected and
skipped if unavailable, matching this codebase's pattern for tests
exercising optional heavy dependencies.
"""
import pytest

torch = pytest.importorskip("torch")

from ollama_arena.simulations.training.imitation import (
    ImitationConfig, default_featurize, train_imitation,
)


def _synthetic_rows(n=60):
    """tick % 3 deterministically picks the action kind -- a trivially
    learnable pattern (the model only needs to learn a near-linear
    boundary on `tick`, which is already in default_featurize's output),
    used purely to prove the training loop reduces loss, not to claim any
    real-world predictive power."""
    kinds = ["work", "rest", "spend"]
    rows = []
    for i in range(n):
        rows.append({
            "tick": i, "reward": 0.0, "terminated": False, "truncated": False,
            "obs": {"visible_event_ids": list(range(i % 4))},
            "action": {"kind": kinds[i % 3]},
        })
    return rows


def test_train_imitation_reduces_loss_over_epochs():
    rows = _synthetic_rows()
    result = train_imitation(rows, config=ImitationConfig(seed=0, epochs=15, batch_size=8, lr=0.05))
    assert len(result.losses_by_epoch) == 15
    assert result.losses_by_epoch[-1] < result.losses_by_epoch[0]


def test_train_imitation_is_deterministic_given_a_seed():
    rows = _synthetic_rows()
    r1 = train_imitation(rows, config=ImitationConfig(seed=42, epochs=5))
    r2 = train_imitation(rows, config=ImitationConfig(seed=42, epochs=5))
    assert r1.losses_by_epoch == pytest.approx(r2.losses_by_epoch)


def test_train_imitation_rejects_empty_dataset():
    with pytest.raises(ValueError, match="no transitions"):
        train_imitation([], config=ImitationConfig())


def test_train_imitation_rejects_single_action_kind():
    rows = [{
        "tick": 0, "reward": 0.0, "terminated": False, "truncated": False,
        "obs": {"visible_event_ids": []}, "action": {"kind": "choose"},
    }]
    with pytest.raises(ValueError, match="at least 2 distinct action kinds"):
        train_imitation(rows, config=ImitationConfig())


def test_train_imitation_result_includes_loadable_state_dict():
    rows = _synthetic_rows()
    result = train_imitation(rows, config=ImitationConfig(seed=0, epochs=3))
    from ollama_arena.simulations.training.policy import build_policy
    model = build_policy(input_dim=5, n_kinds=len(result.kind_vocab))
    model.load_state_dict(result.state_dict)  # must not raise


def test_default_featurize_extracts_generic_fields():
    row = {
        "tick": 3, "reward": 1.0, "terminated": True, "truncated": False,
        "obs": {"visible_event_ids": ["e1", "e2"]}, "action": {"kind": "vote"},
    }
    features, kind = default_featurize(row)
    assert features == [3.0, 1.0, 1.0, 0.0, 2.0]
    assert kind == "vote"


def test_custom_featurizer_is_used_instead_of_default():
    rows = _synthetic_rows()
    calls = []

    def tracking_featurize(row):
        calls.append(row)
        return default_featurize(row)

    train_imitation(rows, config=ImitationConfig(seed=0, epochs=1), featurize=tracking_featurize)
    assert len(calls) == len(rows)
