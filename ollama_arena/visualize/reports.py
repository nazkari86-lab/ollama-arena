"""Generators for single-match and single-royale reports (JSON/HTML)."""
from __future__ import annotations
import html
import json
import datetime
from pathlib import Path

def export_match_report(
    match_id: int,
    info: dict,
    tasks: list[dict],
    out_dir: str = "reports",
) -> str:
    """Export a detailed report for one match (Duel)."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    
    # 1. JSON Export
    report_data = {
        "match_id": match_id,
        "type": "duel",
        "model_a": info["model_a"],
        "model_b": info["model_b"],
        "category": info["category"],
        "ts": info["ts"],
        "summary": {
            "score_a": info["score_a"],
            "score_b": info["score_b"],
            "elo_a_after": info["elo_a_after"],
            "elo_b_after": info["elo_b_after"],
        },
        "tasks": tasks
    }
    
    json_path = Path(out_dir) / f"match_{match_id}.json"
    json_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
    
    # 2. HTML Export
    html_path = Path(out_dir) / f"match_{match_id}.html"
    
    rows = []
    for t in tasks:
        outcome_color = "#3fb950" if t["outcome"] == "a_wins" else "#f85149" if t["outcome"] == "b_wins" else "#8b949e"
        rows.append(f"""
            <div class="task-card">
                <div class="task-header">
                    <span class="task-id">{html.escape(str(t['task_id']))}</span>
                    <span class="outcome" style="color: {outcome_color}">{html.escape(t['outcome'].replace('_', ' ').upper())}</span>
                </div>
                <div class="instruction">{html.escape(str(t['instruction']))}</div>
                <div class="responses">
                    <div class="resp-box">
                        <div class="resp-header">{html.escape(str(info['model_a']))} ({t['score_a']})</div>
                        <pre><code>{html.escape(str(t['response_a']))}</code></pre>
                    </div>
                    <div class="resp-box">
                        <div class="resp-header">{html.escape(str(info['model_b']))} ({t['score_b']})</div>
                        <pre><code>{html.escape(str(t['response_b']))}</code></pre>
                    </div>
                </div>
                {f'<div class="expected">Expected: {html.escape(str(t["expected"]))}</div>' if t.get("expected") else ""}
            </div>
        """)
    
    ts_str = datetime.datetime.fromtimestamp(info["ts"]).strftime("%Y-%m-%d %H:%M:%S")
    
    html_content = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Match #{match_id} Report</title>
<style>
    body {{ background: #0d1117; color: #e6edf3; font-family: system-ui; padding: 40px; line-height: 1.6; }}
    .container {{ max-width: 1000px; margin: 0 auto; }}
    h1 {{ border-bottom: 1px solid #30363d; padding-bottom: 10px; }}
    .meta {{ color: #8b949e; margin-bottom: 30px; }}
    .summary {{ display: flex; gap: 20px; margin-bottom: 40px; }}
    .stat-card {{ background: #161b22; border: 1px solid #30363d; padding: 20px; border-radius: 8px; flex: 1; text-align: center; }}
    .stat-val {{ font-size: 24px; font-weight: bold; color: #58a6ff; }}
    .task-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
    .task-header {{ display: flex; justify-content: space-between; margin-bottom: 15px; border-bottom: 1px solid #21262d; padding-bottom: 10px; }}
    .task-id {{ font-weight: bold; color: #e3b341; }}
    .instruction {{ font-style: italic; color: #8b949e; margin-bottom: 20px; }}
    .responses {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
    .resp-box {{ background: #0d1117; border: 1px solid #21262d; border-radius: 4px; padding: 15px; }}
    .resp-header {{ font-weight: bold; margin-bottom: 10px; color: #58a6ff; border-bottom: 1px solid #21262d; }}
    pre {{ white-space: pre-wrap; word-break: break-all; font-family: monospace; font-size: 13px; }}
    .expected {{ margin-top: 15px; color: #e3b341; font-size: 14px; }}
</style></head>
<body>
    <div class="container">
        <h1>Match #{match_id} Report</h1>
        <div class="meta">
            Model A: <b>{html.escape(str(info['model_a']))}</b> | Model B: <b>{html.escape(str(info['model_b']))}</b> | Category: <b>{html.escape(str(info['category']))}</b><br>
            Timestamp: {ts_str}
        </div>
        <div class="summary">
            <div class="stat-card">
                <div>{html.escape(str(info['model_a']))} Score</div>
                <div class="stat-val">{info['score_a']}</div>
            </div>
            <div class="stat-card">
                <div>{html.escape(str(info['model_b']))} Score</div>
                <div class="stat-val">{info['score_b']}</div>
            </div>
        </div>
        
        <h2>Per-Task Details</h2>
        {''.join(rows)}
    </div>
</body></html>
"""
    html_path.write_text(html_content, encoding="utf-8")
    return str(html_path)


def export_royale_report(
    royale_id: int,
    category: str,
    models: list[str],
    tasks: list[dict],
    out_dir: str = "reports",
) -> str:
    """Export a detailed report for one Battle Royale (N-way)."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    
    # tasks in royale_entries are grouped by task_id
    tasks_grouped: dict[str, list[dict]] = {}
    for entry in tasks:
        tid = entry["task_id"]
        tasks_grouped.setdefault(tid, []).append(entry)
        
    # 1. JSON Export
    report_data = {
        "royale_id": royale_id,
        "type": "royale",
        "models": models,
        "category": category,
        "tasks": tasks_grouped
    }
    json_path = Path(out_dir) / f"royale_{royale_id}.json"
    json_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
    
    # 2. HTML Export
    html_path = Path(out_dir) / f"royale_{royale_id}.html"
    
    task_sections = []
    for tid, entries in tasks_grouped.items():
        # Sort by rank
        entries.sort(key=lambda x: x["rank"])
        
        # Get instruction from first entry if available (need to make sure it's saved)
        # Wait, the royale_entries table doesn't have instruction. I should have added it.
        # But for now, we'll just show the task_id.
        
        model_responses = []
        for e in entries:
            model_responses.append(f"""
                <div class="resp-box">
                    <div class="resp-header">#{e['rank']} {html.escape(str(e['model']))} (Score: {e['score']})</div>
                    <pre><code>{html.escape(str(e['response']))}</code></pre>
                </div>
            """)

        task_sections.append(f"""
            <div class="task-card">
                <div class="task-header">
                    <span class="task-id">{html.escape(str(tid))}</span>
                </div>
                <div class="responses-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 15px;">
                    {''.join(model_responses)}
                </div>
            </div>
        """)
        
    html_content = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Battle Royale #{royale_id} Report</title>
<style>
    body {{ background: #0d1117; color: #e6edf3; font-family: system-ui; padding: 40px; line-height: 1.6; }}
    .container {{ max-width: 1200px; margin: 0 auto; }}
    h1 {{ border-bottom: 1px solid #30363d; padding-bottom: 10px; }}
    .meta {{ color: #8b949e; margin-bottom: 30px; }}
    .task-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 30px; }}
    .task-header {{ font-weight: bold; margin-bottom: 15px; border-bottom: 1px solid #21262d; padding-bottom: 10px; color: #e3b341; }}
    .resp-box {{ background: #0d1117; border: 1px solid #21262d; border-radius: 4px; padding: 12px; }}
    .resp-header {{ font-weight: bold; margin-bottom: 8px; color: #58a6ff; font-size: 13px; }}
    pre {{ white-space: pre-wrap; word-break: break-all; font-family: monospace; font-size: 12px; }}
</style></head>
<body>
    <div class="container">
        <h1>Battle Royale #{royale_id} Report</h1>
        <div class="meta">
            Models: <b>{html.escape(', '.join(str(m) for m in models))}</b> | Category: <b>{html.escape(str(category))}</b>
        </div>
        
        <h2>Match Details</h2>
        {''.join(task_sections)}
    </div>
</body></html>
"""
    html_path.write_text(html_content, encoding="utf-8")
    return str(html_path)
