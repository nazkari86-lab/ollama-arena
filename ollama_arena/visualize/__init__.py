"""
Plotly chart generators for arena results.

    elo_timeline_html     ELO rating evolution per model over time
    radar_html            Win-rate per category
    heatmap_html          Head-to-head win-rate matrix
    performance_chart_html  Throughput vs latency
    leaderboard_table_html  Static HTML leaderboard
    full_dashboard_html   All of the above in one document
    export_dashboard      Write the full dashboard to disk
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
