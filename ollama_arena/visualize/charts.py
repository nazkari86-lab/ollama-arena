"""Plotly chart generators returning embeddable HTML fragments."""
from __future__ import annotations
import datetime, json, math
from collections import defaultdict
from pathlib import Path


def _require_plotly():
    try:
        import plotly.graph_objects as go
        return go
    except ImportError:
        raise RuntimeError(
            "Install plotly to generate charts:\n"
            "    pip install 'ollama-arena[viz]'"
        )


# ELO timeline
def elo_timeline_html(matches: list[dict], top_n: int = 8) -> str:
    """
    Plot ELO rating evolution for each model over time.

    Args:
        matches:  list from EloStore.match_history() (most recent first OK)
        top_n:    show only the top N models by matches played
    """
    go = _require_plotly()
    series: dict[str, list[tuple[float, float]]] = defaultdict(list)

    # Walk in chronological order to build per-model curves
    ms = sorted(matches, key=lambda m: m.get("ts", 0))
    for m in ms:
        ts = m["ts"]
        series[m["model_a"]].append((ts, m["elo_a_after"]))
        series[m["model_b"]].append((ts, m["elo_b_after"]))

    # Filter to top by match count
    sorted_models = sorted(series.keys(), key=lambda k: -len(series[k]))[:top_n]

    fig = go.Figure()
    colors = ["#58a6ff", "#3fb950", "#f85149", "#e3b341", "#bc8cff",
              "#79c0ff", "#56d364", "#ff7b72", "#d29922", "#a371f7"]
    for i, model in enumerate(sorted_models):
        pts = series[model]
        xs = [datetime.datetime.fromtimestamp(t).strftime("%m-%d %H:%M") for t, _ in pts]
        ys = [v for _, v in pts]
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="lines+markers", name=model,
            line=dict(width=2.5, color=colors[i % len(colors)]),
            marker=dict(size=5),
        ))

    fig.update_layout(
        title=dict(text="ELO Rating Over Time", font=dict(size=20, color="#e6edf3")),
        plot_bgcolor="#161b22", paper_bgcolor="#0d1117",
        font=dict(color="#e6edf3", family="system-ui"),
        xaxis=dict(showgrid=True, gridcolor="#30363d", title="Match #"),
        yaxis=dict(showgrid=True, gridcolor="#30363d", title="ELO Rating"),
        legend=dict(bgcolor="#161b22", bordercolor="#30363d", borderwidth=1),
        height=460, margin=dict(l=60, r=40, t=60, b=60),
        hovermode="x unified",
    )
    return fig.to_html(include_plotlyjs="cdn", full_html=False,
                      div_id="elo-timeline-chart")


# Radar (capability by category)
def radar_html(matches: list[dict], categories: list[str], top_n: int = 5) -> str:
    """Radar chart of each model's win-rate per category."""
    go = _require_plotly()

    # model → category → (wins, total)
    per: dict[str, dict[str, list[int]]] = defaultdict(
        lambda: defaultdict(lambda: [0, 0])
    )
    for m in matches:
        c = m.get("category", "?")
        wins_a = 1 if m["score_a"] > m["score_b"] else 0
        wins_b = 1 if m["score_b"] > m["score_a"] else 0
        per[m["model_a"]][c][0] += wins_a
        per[m["model_a"]][c][1] += 1
        per[m["model_b"]][c][0] += wins_b
        per[m["model_b"]][c][1] += 1

    # Top N by total matches
    sorted_models = sorted(per.keys(),
                           key=lambda k: -sum(v[1] for v in per[k].values()))[:top_n]

    fig = go.Figure()
    for model in sorted_models:
        values = []
        for cat in categories:
            wins, total = per[model].get(cat, [0, 0])
            values.append(round(wins / total, 3) if total else 0.0)
        # Close the loop
        values.append(values[0])
        labels = categories + [categories[0]]
        fig.add_trace(go.Scatterpolar(
            r=values, theta=labels, fill="toself", name=model, opacity=0.55,
        ))

    fig.update_layout(
        title=dict(text="Capability Radar (win-rate per category)",
                   font=dict(size=18, color="#e6edf3")),
        plot_bgcolor="#0d1117", paper_bgcolor="#0d1117",
        font=dict(color="#e6edf3"),
        polar=dict(
            bgcolor="#161b22",
            radialaxis=dict(visible=True, range=[0, 1], gridcolor="#30363d",
                            tickfont=dict(color="#8b949e")),
            angularaxis=dict(gridcolor="#30363d", tickfont=dict(color="#e6edf3")),
        ),
        showlegend=True, height=450,
        legend=dict(bgcolor="#161b22", bordercolor="#30363d", borderwidth=1),
        margin=dict(l=40, r=40, t=60, b=40),
    )
    return fig.to_html(include_plotlyjs=False, full_html=False, div_id="radar-chart")


# Head-to-head heatmap
def heatmap_html(matches: list[dict]) -> str:
    """Heatmap of pairwise win-rates between models."""
    go = _require_plotly()

    pair: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for m in matches:
        a, b = m["model_a"], m["model_b"]
        if m["score_a"] > m["score_b"]:
            pair[(a, b)][0] += 1
        elif m["score_b"] > m["score_a"]:
            pair[(b, a)][0] += 1
        pair[(a, b)][1] += 1
        pair[(b, a)][1] += 1

    models = sorted({m for k in pair.keys() for m in k})
    z = []
    for i, ra in enumerate(models):
        row = []
        for j, rb in enumerate(models):
            if ra == rb:
                row.append(None)
            else:
                wins, total = pair.get((ra, rb), [0, 0])
                row.append(round(wins / total, 3) if total else None)
        z.append(row)

    fig = go.Figure(data=go.Heatmap(
        z=z, x=models, y=models,
        colorscale="RdYlGn", zmin=0, zmax=1,
        text=[[(f"{v:.0%}" if v is not None else "") for v in row] for row in z],
        texttemplate="%{text}", hoverongaps=False,
        colorbar=dict(title="Win Rate", tickfont=dict(color="#e6edf3")),
    ))
    fig.update_layout(
        title=dict(text="Head-to-Head Win Rate", font=dict(size=18, color="#e6edf3")),
        plot_bgcolor="#0d1117", paper_bgcolor="#0d1117",
        font=dict(color="#e6edf3"),
        xaxis=dict(side="bottom", title="Opponent"),
        yaxis=dict(title="Model", autorange="reversed"),
        height=480, margin=dict(l=120, r=60, t=60, b=120),
    )
    return fig.to_html(include_plotlyjs=False, full_html=False, div_id="heatmap-chart")


# Performance
def performance_chart_html(perf: list[dict] | dict) -> str:
    """
    Bar chart of mean tokens/sec and latency per model.

    perf items: {model, tps_mean, tps_p95, latency_mean_s, latency_p95_s}
    Accepts export_summary dict with a ``models`` key.
    """
    go = _require_plotly()
    if isinstance(perf, dict):
        perf = perf.get("models") or []
    if not perf:
        return "<div style='color:#8b949e;padding:20px;text-align:center'>No performance data yet.</div>"

    perf = sorted(perf, key=lambda p: -p.get("tps_mean", 0))
    models = [p["model"] for p in perf]
    tps = [p.get("tps_mean", 0) for p in perf]
    lat = [p.get("latency_mean_s", 0) for p in perf]

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Tokens/sec", x=models, y=tps, marker_color="#58a6ff",
                         yaxis="y", offsetgroup=1))
    fig.add_trace(go.Bar(name="Avg latency (s)", x=models, y=lat, marker_color="#f85149",
                         yaxis="y2", offsetgroup=2))
    fig.update_layout(
        title=dict(text="Throughput vs Latency", font=dict(size=18, color="#e6edf3")),
        plot_bgcolor="#161b22", paper_bgcolor="#0d1117",
        font=dict(color="#e6edf3"),
        xaxis=dict(title="Model"),
        yaxis=dict(title="Tokens/sec", side="left", gridcolor="#30363d",
                   titlefont=dict(color="#58a6ff"), tickfont=dict(color="#58a6ff")),
        yaxis2=dict(title="Latency (s)", side="right", overlaying="y",
                    titlefont=dict(color="#f85149"), tickfont=dict(color="#f85149")),
        barmode="group", height=420,
        legend=dict(bgcolor="#161b22", bordercolor="#30363d", borderwidth=1),
    )
    return fig.to_html(include_plotlyjs=False, full_html=False, div_id="perf-chart")


# Leaderboard table (rendered as HTML, not Plotly)
def leaderboard_table_html(board: list[dict]) -> str:
    if not board:
        return "<div style='color:#8b949e;padding:20px;text-align:center'>No matches yet.</div>"
    _trend_icon = {"up": "▲", "down": "▼", "stable": "—"}
    _trend_color = {"up": "#3fb950", "down": "#f85149", "stable": "#8b949e"}
    rows = []
    for e in board:
        wr = f"{e['win_rate']:.0%}"
        trend = e.get("trend", "stable")
        delta = e.get("trend_delta", 0.0)
        icon = _trend_icon.get(trend, "—")
        tcolor = _trend_color.get(trend, "#8b949e")
        trend_cell = (
            f"<span style='color:{tcolor};font-weight:700' title='Last-5 ELO Δ: {delta:+.1f}'>"
            f"{icon} {abs(delta):.0f}</span>"
        )
        rows.append(
            f"<tr>"
            f"<td style='font-weight:700;padding:8px 10px'>{e['rank']}</td>"
            f"<td style='padding:8px 10px'><strong>{e['model']}</strong></td>"
            f"<td style='color:#58a6ff;font-weight:700;padding:8px 10px'>{e['elo']:.0f}</td>"
            f"<td style='padding:8px 10px'>{trend_cell}</td>"
            f"<td style='color:#3fb950;padding:8px 10px'>{e['wins']}</td>"
            f"<td style='color:#f85149;padding:8px 10px'>{e['losses']}</td>"
            f"<td style='color:#8b949e;padding:8px 10px'>{e['draws']}</td>"
            f"<td style='padding:8px 10px'>{e['matches']}</td>"
            f"<td style='padding:8px 10px'>{wr}</td>"
            f"</tr>"
        )
    table = (
        "<table style='width:100%;border-collapse:collapse'>"
        "<thead><tr style='border-bottom:1px solid #30363d'>"
        "<th style='text-align:left;padding:10px'>Rank</th>"
        "<th style='text-align:left;padding:10px'>Model</th>"
        "<th style='padding:10px'>ELO</th>"
        "<th style='padding:10px'>Trend</th>"
        "<th style='padding:10px'>W</th>"
        "<th style='padding:10px'>L</th>"
        "<th style='padding:10px'>D</th>"
        "<th style='padding:10px'>Matches</th>"
        "<th style='padding:10px'>Win%</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )
    return table


def anti_leaderboard_table_html(board: list[dict]) -> str:
    if not board:
        return "<div style='color:#8b949e;padding:20px;text-align:center'>No hallucination data yet.</div>"
    rows = []
    for e in board:
        rate = f"{e['halluc_rate']:.1%}"
        color = "#f85149" if e["halluc_rate"] > 0.2 else ("#e3b341" if e["halluc_rate"] > 0.05 else "#3fb950")
        rows.append(
            f"<tr>"
            f"<td style='font-weight:700'>{e['rank']}</td>"
            f"<td><strong>{e['model']}</strong></td>"
            f"<td style='color:{color};font-weight:800'>{rate}</td>"
            f"<td>{e['hallucinations']}</td>"
            f"<td>{e['total_checked']}</td>"
            f"</tr>"
        )
    table = (
        "<table style='width:100%;border-collapse:collapse'>"
        "<thead><tr style='border-bottom:1px solid #30363d'>"
        "<th style='text-align:left;padding:10px'>Rank</th>"
        "<th style='text-align:left;padding:10px'>Model</th>"
        "<th style='padding:10px'>Halluc Rate</th>"
        "<th style='padding:10px'>Count</th>"
        "<th style='padding:10px'>Checked</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )
    return table


# Full dashboard
def full_dashboard_html(
    leaderboard: list[dict],
    matches: list[dict],
    categories: list[str],
    performance: list[dict] | None = None,
    anti_leaderboard: list[dict] | None = None,
    title: str = "Ollama Arena Dashboard",
) -> str:
    """Combine every chart into a self-contained shareable HTML page."""
    perf_chart = performance_chart_html(performance or [])
    elo_chart  = elo_timeline_html(matches) if matches else ""
    radar      = radar_html(matches, categories) if matches else ""
    heatmap    = heatmap_html(matches) if matches else ""
    lb_table   = leaderboard_table_html(leaderboard)
    alb_table  = anti_leaderboard_table_html(anti_leaderboard or [])
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>{title}</title>
<style>
  body {{ background:#0d1117; color:#e6edf3; font-family:system-ui; margin:0; padding:32px; }}
  h1 {{ font-size:28px; margin-bottom:4px; font-weight:600; }}
  h1 span {{ color:#58a6ff; }}
  p.meta {{ color:#8b949e; margin-bottom:24px; font-size:14px; }}
  h2 {{ font-size:13px; color:#8b949e; text-transform:uppercase;
       letter-spacing:0.5px; margin-bottom:12px; font-weight:600; }}
  .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; }}
  .card {{ background:#161b22; border:1px solid #30363d; border-radius:12px; padding:20px; }}
  .full {{ grid-column:1/-1; }}
  table th, table td {{ border-bottom:1px solid #21262d; padding:10px; }}
  table tr:hover td {{ background:#1f2937; }}
  footer {{ margin-top:32px; color:#8b949e; font-size:12px; text-align:center; }}
  a {{ color:#58a6ff; text-decoration:none; }}
</style></head>
<body>
  <h1>Ollama <span>Arena</span></h1>
  <p class="meta">Generated {ts}</p>
  <div class="grid">
    <div class="card full"><h2>Leaderboard</h2>{lb_table}</div>
    <div class="card"><h2>Anti-Leaderboard (Hallucinations)</h2>{alb_table}</div>
    <div class="card">{radar}</div>
    <div class="card full">{elo_chart}</div>
    <div class="card">{heatmap}</div>
    <div class="card">{perf_chart}</div>
  </div>
  <footer>
    <a href="https://github.com/nazkari86-lab/ollama-arena">github.com/nazkari86-lab/ollama-arena</a>
  </footer>
</body></html>
"""


def export_dashboard(
    out_path: str,
    leaderboard: list[dict],
    matches: list[dict],
    categories: list[str],
    performance: list[dict] | None = None,
    anti_leaderboard: list[dict] | None = None,
):
    """Write a standalone shareable HTML dashboard to disk."""
    html = full_dashboard_html(leaderboard, matches, categories, performance, anti_leaderboard)
    Path(out_path).write_text(html, encoding="utf-8")
    return out_path
