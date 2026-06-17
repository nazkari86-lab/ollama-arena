# Web Dashboard

Launch the interactive web-based dashboard using:

```bash
ollama-arena web
```

By default, the dashboard starts on `http://localhost:7860`.

## Features and Tabs

The dashboard consists of six tabs powered by FastAPI, Jinja2 templates, and Plotly visualizations:

1. **Dashboard**:
   * **ELO Leaderboard**: Live standings table.
   * **Radar Chart**: Comparison of model strengths across different categories.
   * **ELO Timeline**: A historical graph showing how ELO ratings changed over time.
   * **Heatmap**: Direct win/loss matrix between all models.

2. **Match**:
   * Configure a match between two models directly from the UI.
   * Choose categories, number of tasks, and start the run.
   * Stream results and logs in real-time as tasks are evaluated.

3. **Inspect**:
   * Browse a task by its ID and compare responses side-by-side with scores.

4. **Report**:
   * Select any model to view its detailed win rates per category along with a summary of its strengths and weaknesses.

5. **Datasets**:
   * Manage and view cached HuggingFace datasets used for evaluations.

6. **Performance**:
   * Analyze TPS (tokens per second), response latency, and TTFT (time-to-first-token) comparisons through scatter plots.
