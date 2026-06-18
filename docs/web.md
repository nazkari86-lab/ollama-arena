# Web Dashboard

Launch the interactive web-based dashboard using:

```bash
ollama-arena web
```

By default, the dashboard starts on `http://localhost:7860`.

## Architecture

The UI is split into modular assets:

| Path | Purpose |
|------|---------|
| `templates/base.html` | Shared head, CDN scripts, CSS/JS includes |
| `templates/index.html` | Dashboard body (extends base) |
| `static/css/arena.css` | Theme, layout, components |
| `static/js/utils.js` | XSS helpers, toasts, theme, telemetry |
| `static/js/ws-client.js` | WebSocket hub, blind mode, pipeline replay |
| `static/js/match.js` | Match, tournament, playground, inspect |
| `static/js/spec.js` | Speculative decoding controls |
| `static/agent_trace.js` | Agent tool-call trace renderer |
| `static/arena3d.js` | Three.js battle visualization |

Static files are served from `/static/*` via FastAPI `StaticFiles`.

## Features and Tabs

The dashboard consists of ten tabs powered by FastAPI, Jinja2 templates, WebSockets, and Plotly:

1. **Dashboard** — ELO leaderboard, radar chart, timeline, heatmap
2. **Match** — Pairwise battles with live streaming and memory-strategy preview
3. **Tournament** — Round-robin between N models
4. **Playground** — Manual A/B prompt testing with agent trace panel
5. **Inspect** — Task drill-down with visual diff (jsdiff)
6. **Report** — Per-model category breakdown
7. **Datasets** — HuggingFace dataset management
8. **Performance** — TPS, latency, TTFT, and per-tool MCP latency
9. **Spec Decode** — Speculative decoding server control and benchmarks
10. **Bench All** — Parallel TPS comparison across spec servers

## Agent Trace

When tasks use MCP tools (`tool_use` category), the UI renders a step-by-step
trace with tool names, arguments, results, latency, and security-gate denials.
The 3D arena view pulses on each tool call via `ThreeJSArena.pulseToolChain()`.

## Security

- Content-Security-Policy restricts script/style sources
- Model output is sanitized with DOMPurify before `innerHTML`
- Rate limits on match/tournament/playground endpoints (requires `slowapi`)
- WebSocket origin validation against `ARENA_ALLOWED_ORIGINS`

## API highlights

| Endpoint | Description |
|----------|-------------|
| `GET /api/perf` | Model TPS/latency + tool latency aggregates |
| `GET /api/agent_trace/{match_id}` | Agent traces for a match |
| `POST /api/strategy` | Memory scheduler preview (CONCURRENT/HOT_SWAP/PIPELINE) |
| `WS /ws` | Live match/tournament event stream |
