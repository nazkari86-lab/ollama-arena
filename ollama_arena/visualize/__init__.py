"""
Visualization layer — Plotly charts for arena results.

  • elo_timeline  — ELO over time per model
  • radar         — Capability radar (per category win-rate)
  • heatmap       — Head-to-head win-rate matrix
  • performance   — tokens/sec, latency p50/p95
  • dashboard     — generate self-contained HTML with all charts
"""
from .charts import (
    elo_timeline_html, radar_html, heatmap_html,
    performance_chart_html, leaderboard_table_html,
    full_dashboard_html, export_dashboard,
)

__all__ = [
    "elo_timeline_html", "radar_html", "heatmap_html",
    "performance_chart_html", "leaderboard_table_html",
    "full_dashboard_html", "export_dashboard",
]
