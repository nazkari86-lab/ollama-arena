"""Build SFT/DPO datasets by distilling a stronger teacher model."""
from __future__ import annotations
import json, logging, sqlite3
from pathlib import Path

from ..tasks import get_task, get_tasks
from .analyzer import analyze_task_failures

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


def _failed_task_records(
    weak_model: str,
    category: str,
    db_path: str,
    n_tasks: int,
) -> list[dict]:
    failures = analyze_task_failures(
        db_path=db_path,
        model=weak_model,
        category=category,
    )
    if failures:
        return failures[:n_tasks]

    log.info("[finetune/gen] no task_detail failures — falling back to built-in tasks")
    return [{"task_id": t["id"], "instruction": t["instruction"]}
            for t in get_tasks(category=category, limit=n_tasks)]


def build_training_dataset(
    weak_model: str,
    category: str,
    db_path: str = "arena.db",
    teacher_model: str | None = None,
    backend=None,
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

    records = _failed_task_records(weak_model, category, db_path, n_tasks)
    dataset = []
    for rec in records:
        task = get_task(rec["task_id"])
        prompt = rec.get("instruction") or (task or {}).get("instruction", "")
        if not prompt:
            continue
        res = backend.generate(teacher, prompt)
        if not res.ok:
            continue
        dataset.append({
            "instruction": prompt,
            "input":       "",
            "output":      res.text,
            "task_id":     rec["task_id"],
        })
    log.info(f"[finetune/gen] built {len(dataset)} SFT pairs from {len(records)} failed tasks")
    return dataset


def build_dpo_dataset(
    weak_model: str,
    category: str,
    db_path: str = "arena.db",
    teacher_model: str | None = None,
    backend=None,
    n_tasks: int = 50,
) -> list[dict]:
    """Build preference pairs: chosen=teacher, rejected=weak model's past response."""
    teacher = teacher_model or _top_model_for_category(db_path, category)
    if not teacher:
        raise RuntimeError(f"No teacher model found for category '{category}'")
    if teacher == weak_model:
        raise RuntimeError("Teacher == student. Pass --teacher to override.")
    if backend is None:
        from ..backends.auto import auto_backend
        backend = auto_backend()

    failures = analyze_task_failures(db_path=db_path, model=weak_model, category=category)
    failures = failures[:n_tasks]
    if not failures:
        raise RuntimeError(
            f"No task_detail failures for {weak_model!r} in category {category!r}"
        )

    with sqlite3.connect(db_path) as cx:
        rows = cx.execute("""
            SELECT d.task_id, d.instruction, d.response_a, d.response_b,
                   m.model_a, m.model_b, d.score_a, d.score_b
            FROM task_detail d
            JOIN match_log m ON m.id = d.match_id
            WHERE d.category = ?
        """, (category,)).fetchall()

    by_task: dict[str, tuple] = {}
    for task_id, instruction, ra, rb, ma, mb, sa, sb in rows:
        if task_id not in by_task or (sa or 0) + (sb or 0) < sum(by_task[task_id][-2:] or (0, 0)):
            by_task[task_id] = (instruction, ra, rb, ma, mb, sa, sb)

    dataset = []
    for rec in failures:
        tid = rec["task_id"]
        stored = by_task.get(tid)
        if not stored:
            continue
        instruction, ra, rb, ma, mb, sa, sb = stored
        if weak_model == ma:
            rejected = ra or ""
        elif weak_model == mb:
            rejected = rb or ""
        else:
            continue
        if not rejected.strip():
            continue

        res = backend.generate(teacher, instruction)
        if not res.ok or not res.text.strip():
            continue

        dataset.append({
            "prompt": instruction,
            "chosen": res.text,
            "rejected": rejected,
            "task_id": tid,
        })

    log.info(f"[finetune/gen] built {len(dataset)} DPO pairs")
    return dataset


def save_jsonl(records: list[dict], out_path: str) -> str:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return str(p)
