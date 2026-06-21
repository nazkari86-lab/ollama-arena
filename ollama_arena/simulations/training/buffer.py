"""In-memory trajectory buffer -- append-only list of transition dicts,
flushable to the same JSONL shape dataset.py reads.

Deliberately simple (DI-engine's plain-list TrajBuffer, not SB3's
preallocated circular-buffer machinery): this subsystem runs at CPU/local
scale, not at the throughput a circular buffer exists to support. Reuses
storage.SimStore's exact serialization helpers rather than duplicating the
obs/action -> JSON-safe-dict logic a second time.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..core.types import Transition
from ..storage import _action_to_json, _obs_to_json


class TrajectoryBuffer:
    def __init__(self):
        self._rows: list[dict] = []

    def add(self, transition: Transition) -> None:
        self._rows.append({
            "tick": transition.tick,
            "agent_id": transition.agent_id,
            "obs": json.loads(_obs_to_json(transition.obs)),
            "action": json.loads(_action_to_json(transition.action)),
            "reward": transition.reward,
            "terminated": transition.terminated,
            "truncated": transition.truncated,
            "info": transition.info,
        })

    def __len__(self) -> int:
        return len(self._rows)

    def rows(self) -> list[dict]:
        return list(self._rows)

    def flush_to_jsonl(self, path: str) -> int:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            for row in self._rows:
                f.write(json.dumps(row) + "\n")
        return len(self._rows)
