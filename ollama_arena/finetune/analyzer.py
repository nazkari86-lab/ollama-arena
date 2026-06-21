from __future__ import annotations
import sqlite3
from collections import defaultdict


def analyze_weaknesses(db_path: str = "arena.db",
                       min_matches: int = 3) -> list[dict]:
    """Sub-50% (model, category) pairs with at least `min_matches` games."""
    with sqlite3.connect(db_path) as cx:
        rows = cx.execute("""
            SELECT model_a, model_b, category, score_a, score_b
            FROM match_log
        """).fetchall()

    stats: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])  # [wins, total]
    for ma, mb, cat, sa, sb in rows:
        if sa is None or sb is None:
            continue  # incomplete/errored match — no scores to compare
        if sa > sb:
            stats[(ma, cat)][0] += 1
        elif sb > sa:
            stats[(mb, cat)][0] += 1
        stats[(ma, cat)][1] += 1
        stats[(mb, cat)][1] += 1

    weak = []
    for (model, cat), (wins, total) in stats.items():
        if total < min_matches:
            continue
        wr = wins / total
        if wr < 0.5:
            weak.append({
                "model":     model,
                "category":  cat,
                "win_rate":  round(wr, 3),
                "samples":   total,
                "wins":      wins,
                "gap":       round(0.5 - wr, 3),
            })
    return sorted(weak, key=lambda w: (-w["gap"], -w["samples"]))


def analyze_task_failures(
    db_path: str = "arena.db",
    model: str | None = None,
    category: str | None = None,
    score_threshold: float = 0.5,
    min_samples: int = 1,
) -> list[dict]:
    """Task-level failures from task_detail — where a model scored below threshold or lost."""
    query = """
        SELECT d.task_id, d.category, d.instruction, d.score_a, d.score_b,
               m.model_a, m.model_b, d.outcome
        FROM task_detail d
        JOIN match_log m ON m.id = d.match_id
    """
    params: list = []
    clauses = []
    if category:
        clauses.append("d.category = ?")
        params.append(category)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)

    with sqlite3.connect(db_path) as cx:
        rows = cx.execute(query, params).fetchall()

    agg: dict[tuple[str, str], dict] = {}
    for task_id, cat, instruction, sa, sb, ma, mb, outcome in rows:
        for side_model, score, opp_score in ((ma, sa, sb), (mb, sb, sa)):
            if model and side_model != model:
                continue
            if score is None:
                continue
            if score >= score_threshold and score >= opp_score:
                continue
            key = (side_model, task_id)
            rec = agg.get(key)
            if rec is None:
                agg[key] = {
                    "model": side_model,
                    "task_id": task_id,
                    "category": cat,
                    "instruction": instruction,
                    "avg_score": float(score),
                    "samples": 1,
                    "losses": 1 if score < opp_score else 0,
                }
            else:
                rec["samples"] += 1
                rec["avg_score"] = round(
                    (rec["avg_score"] * (rec["samples"] - 1) + float(score)) / rec["samples"],
                    3,
                )
                if score < opp_score:
                    rec["losses"] += 1

    failures = [v for v in agg.values() if v["samples"] >= min_samples]
    return sorted(failures, key=lambda f: (f["avg_score"], -f["losses"]))


def weakness_report(db_path: str = "arena.db") -> str:
    weak = analyze_weaknesses(db_path)
    if not weak:
        return "No fine-tuning candidates yet — every model wins ≥50%."
    lines = ["model                          category       win%   samples"]
    lines.append("-" * 66)
    for w in weak[:15]:
        lines.append(
            f"{w['model']:30s} {w['category']:12s} {w['win_rate']:6.0%}   {w['samples']}"
        )
    return "\n".join(lines)


def task_failure_report(
    db_path: str = "arena.db",
    model: str | None = None,
    category: str | None = None,
    limit: int = 15,
) -> str:
    failures = analyze_task_failures(db_path, model=model, category=category)
    if not failures:
        return "No task-level failures recorded yet."
    lines = ["task_id              category       avg_score  losses  model"]
    lines.append("-" * 72)
    for f in failures[:limit]:
        lines.append(
            f"{f['task_id']:20s} {f['category']:12s} {f['avg_score']:9.3f}  "
            f"{f['losses']:5d}  {f['model']}"
        )
    return "\n".join(lines)
