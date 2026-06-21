"""Minimal PyTorch policy network for imitation learning over a scenario's
action-kind distribution.

Deliberately small: this isn't trying to compete with a full RL framework,
it answers "can a local model's behavior be cloned/nudged from its own
simulation transcripts." Input/output dims are configured at construction
time from whatever featurizer + action-kind vocabulary the caller used in
imitation.py -- no scenario-specific architecture lives here.
"""
from __future__ import annotations


def build_policy(input_dim: int, n_kinds: int, hidden_dim: int = 32):
    """Lazy torch import -- only training code needs this module at all."""
    try:
        from torch import nn
    except ImportError as e:
        raise RuntimeError(
            "PyTorch is required for simulation training.\n"
            "    pip install 'ollama-arena[finetune]'\n"
            f"({e})"
        ) from e

    return nn.Sequential(
        nn.Linear(input_dim, hidden_dim),
        nn.ReLU(),
        nn.Linear(hidden_dim, n_kinds),
    )
