"""Supervised imitation learning: predict an agent's action kind from a
feature vector of its observation/transition context.

Deliberately decoupled from simulations.core.world -- this file only ever
imports the dataset/buffer format (a list of plain transition dicts), never
the World/Scenario classes, so the simulation runtime and the training
pipeline can evolve independently (the stable-baselines3-style
collect_rollouts()/train() split this whole subsystem is modeled on).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable

Featurizer = Callable[[dict], tuple[list[float], str]]


def default_featurize(transition: dict) -> tuple[list[float], str]:
    """Generic, scenario-agnostic featurizer using only fields every
    Transition has regardless of scenario: tick, reward, terminated,
    truncated, and how many events the agent had witnessed so far.

    This is intentionally minimal -- it makes no claim to being a strong
    feature set, just a real one that works unmodified for any scenario.
    A scenario-aware featurizer (reading Mafia's role/phase, or Sims-
    world's needs/money) will train a far more useful policy; callers are
    expected to supply one of those via the `featurize` parameter for
    anything beyond proving the training loop itself works.
    """
    obs = transition["obs"]
    return (
        [
            float(transition["tick"]),
            float(transition["reward"]),
            float(transition["terminated"]),
            float(transition["truncated"]),
            float(len(obs.get("visible_event_ids", []))),
        ],
        transition["action"]["kind"],
    )


@dataclass
class ImitationConfig:
    seed: int = 0
    batch_size: int = 8
    epochs: int = 5
    lr: float = 1e-2
    hidden_dim: int = 32
    device: str = "cpu"  # CPU by default; opt in to "cuda"/"mps" explicitly


@dataclass
class ImitationResult:
    final_loss: float
    losses_by_epoch: list[float] = field(default_factory=list)
    kind_vocab: list[str] = field(default_factory=list)
    state_dict: dict = field(default_factory=dict)


def train_imitation(
    rows: list[dict],
    config: ImitationConfig | None = None,
    featurize: Featurizer = default_featurize,
) -> ImitationResult:
    """Train a tiny classifier to predict action.kind from `featurize`'s
    output (defaults to a generic, scenario-agnostic feature set -- see
    default_featurize's docstring for what that trades away).

    Runs on CPU by default per this subsystem's "must work on limited local
    hardware" requirement; only set config.device to "cuda"/"mps" if the
    caller has already confirmed one is available (see training.gpu).
    """
    try:
        import torch
        from torch import nn
    except ImportError as e:
        raise RuntimeError(
            "PyTorch is required for simulation training.\n"
            "    pip install 'ollama-arena[finetune]'\n"
            f"({e})"
        ) from e

    from .policy import build_policy

    if not rows:
        raise ValueError("no transitions to train on")

    config = config or ImitationConfig()
    torch.manual_seed(config.seed)
    rng = random.Random(config.seed)

    features, kinds = [], []
    for row in rows:
        feat, kind = featurize(row)
        features.append(feat)
        kinds.append(kind)
    kind_vocab = sorted(set(kinds))
    if len(kind_vocab) < 2:
        raise ValueError(
            f"need at least 2 distinct action kinds to train a classifier, got {kind_vocab!r}"
        )
    kind_to_idx = {k: i for i, k in enumerate(kind_vocab)}

    X = torch.tensor(features, dtype=torch.float32, device=config.device)
    y = torch.tensor([kind_to_idx[k] for k in kinds], dtype=torch.long, device=config.device)

    model = build_policy(input_dim=X.shape[1], n_kinds=len(kind_vocab), hidden_dim=config.hidden_dim)
    model.to(config.device)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.lr)
    loss_fn = nn.CrossEntropyLoss()

    n = X.shape[0]
    losses_by_epoch: list[float] = []
    for _epoch in range(config.epochs):
        order = list(range(n))
        rng.shuffle(order)
        epoch_loss = 0.0
        n_batches = 0
        for start in range(0, n, config.batch_size):
            idx = order[start:start + config.batch_size]
            batch_X = X[idx]
            batch_y = y[idx]
            optimizer.zero_grad()
            logits = model(batch_X)
            loss = loss_fn(logits, batch_y)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item()
            n_batches += 1
        losses_by_epoch.append(epoch_loss / max(1, n_batches))

    return ImitationResult(
        final_loss=losses_by_epoch[-1] if losses_by_epoch else float("nan"),
        losses_by_epoch=losses_by_epoch,
        kind_vocab=kind_vocab,
        state_dict={k: v.detach().cpu().clone() for k, v in model.state_dict().items()},
    )
