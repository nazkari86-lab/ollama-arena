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
