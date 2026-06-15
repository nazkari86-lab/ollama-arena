"""
Build training datasets from arena failures.

For each task the weak model failed at, generate a high-quality response
from the strongest model in that category, then save (instruction, response)
pairs as JSONL for Unsloth/transformers fine-tuning.
"""
from __future__ import annotations
import json, logging, sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Callable

from ..tasks import get_tasks

log = logging.getLogger("arena.finetune.gen")


def _top_model_for_category(db_path: str, category: str) -> str | None:
    """Return the highest-ELO model that has played the given category."""
    with sqlite3.connect(db_path) as cx:
        rows = cx.execute("""
            SELECT model_a, MAX(elo_a_after) FROM match_log
            WHERE category=? GROUP BY model_a
            UNION
            SELECT model_b, MAX(elo_b_after) FROM match_log
            WHERE category=? GROUP BY model_b
        """, (category, category)).fetchall()
    if not rows:
        return None
    by_model: dict[str, float] = {}
    for m, e in rows:
        by_model[m] = max(by_model.get(m, 0), e or 0)
    return max(by_model.items(), key=lambda x: x[1])[0]


def build_training_dataset(
    weak_model: str,
    category: str,
    db_path: str = "arena.db",
    teacher_model: str | None = None,
    backend = None,                 # ollama_arena.backends.base.Backend
    n_tasks: int = 50,
) -> list[dict]:
    """
    Build (instruction, response) pairs by asking a strong teacher model to
    solve tasks the weak model failed at.

    Returns list of {"instruction": ..., "input": "", "output": ...}.
    """
    teacher = teacher_model or _top_model_for_category(db_path, category)
    if not teacher:
        raise RuntimeError(f"No teacher model found for category '{category}'")
    if teacher == weak_model:
        raise RuntimeError("Teacher == student. Pass --teacher to override.")
    if backend is None:
        from ..backends.auto import auto_backend
        backend = auto_backend()

    log.info(f"[finetune/gen] teacher={teacher}  student={weak_model}  cat={category}")

    tasks = get_tasks(category=category, limit=n_tasks)
    dataset = []
    for t in tasks:
        prompt = t["instruction"]
        res = backend.generate(teacher, prompt)
        if not res.ok:
            continue
        dataset.append({
            "instruction": prompt,
            "input":       "",
            "output":      res.text,
            "task_id":     t["id"],
        })
    log.info(f"[finetune/gen] built {len(dataset)} pairs")
    return dataset


def save_jsonl(records: list[dict], out_path: str) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return str(p)
