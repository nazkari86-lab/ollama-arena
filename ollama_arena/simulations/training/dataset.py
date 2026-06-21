"""Export sim.db transitions to JSONL, plus a duck-typed Dataset wrapper.

No top-level torch import: this lets the rest of `simulations/` (core,
scenarios, CLI listing/replay) stay usable without the [finetune] extra
installed -- only code that actually trains (imitation.py/policy.py) needs
torch, and that's imported lazily there.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..storage import SimStore


def export_run_to_jsonl(run_id: str, out_path: str, db_path: str = "sim.db") -> int:
    """Write one JSON line per stored Transition for `run_id`.

    Includes action.raw_llm_output (already preserved end-to-end by
    action_schema.parse_action()) so imitation learning can train on the
    model's actual text output, not just the already-parsed action.
    """
    store = SimStore(db_path)
    transitions = store.get_transitions(run_id)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for t in transitions:
            f.write(json.dumps(t) + "\n")
    return len(transitions)


def load_jsonl(jsonl_path: str) -> list[dict]:
    rows = []
    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


class SimTransitionDataset:
    """Duck-typed for torch.utils.data.DataLoader (__len__ + __getitem__).

    Deliberately does NOT subclass torch.utils.data.Dataset, so importing
    this class has no hard torch dependency -- only code that actually
    trains needs torch installed.
    """
    def __init__(self, jsonl_path: str):
        self._rows = load_jsonl(jsonl_path)

    def __len__(self) -> int:
        return len(self._rows)

    def __getitem__(self, idx: int) -> dict:
        return self._rows[idx]
