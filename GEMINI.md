# ollama-arena — Project Context for AI Assistants

## What this project is

**ollama-arena** is a pair-wise ELO evaluation arena for local LLMs (Ollama, vLLM, LM Studio, OpenAI-compatible APIs).
Users run `ollama-arena match --models llama3.2:3b,qwen2.5-coder:7b` to pit two models head-to-head on built-in tasks,
get ELO ratings, detailed per-task responses, and benchmark scores.

- **PyPI**: `pip install ollama-arena` (published as `nazkari86-lab/ollama-arena` on GitHub)
- **Current version**: 2.4.0
- **CLI entry points**: `ollama-arena` and `llm-arena`

---

## Architecture

```
ollama_arena/
  __init__.py          — public API, version = "2.4.0"
  arena.py             — Arena class, MatchResult dataclass, run_match()
  backends.py          — OllamaBackend, OpenAICompatBackend, TransformersBackend
  cli.py               — all CLI commands (match, benchmark, results, inspect, report, ...)
  elo.py               — EloStore (SQLite), update_elo(), task_detail table, benchmark_runs table
  evaluator.py         — per-task scorers + router: eval_coding, eval_text_answer,
                         eval_security, eval_inspection, eval_planning
  judge.py             — LLMJudge for open-ended (use_judge=True) tasks
  performance.py       — PerfTracker (TPS, latency, TTFT)
  sandboxes.py         — sandboxed code execution (subprocess + deny-list + Docker option)
  web.py               — FastAPI web dashboard
  tasks/
    __init__.py        — ALL_TASKS dict, get_tasks(), task_stats(), list_categories()
    coding.py          — 30 Python coding tasks (code_001..code_030)
    coding_multilang.py — 14 JS/TS/Rust/Go/C++ tasks
    reasoning.py       — 15 reasoning tasks (reas_001..reas_015)
    math.py            — 50 offline math tasks (math_001..math_050)
    knowledge.py       — 50 offline knowledge tasks (know_001..know_050)
    security.py        — 15 security tasks (sec_001..sec_015)
    planning.py        — 20 planning tasks (plan_001..plan_020)
    inspection.py      — 20 code inspection tasks (insp_001..insp_020)
    creative.py        — 15 judge-scored creative tasks (crea_001..crea_015)
templates/
  index.html           — FastAPI Jinja2 web UI (dark GitHub-style, Plotly charts, 6 tabs)
static/                — CSS/JS assets
tests/
  test_smoke.py        — 21 smoke tests (all passing, run: pytest tests/ -q)
examples/
  github_actions/llm-benchmark.yml  — CI template with --fail-below score gate
```

**Total tasks: 229** across 8 categories.

---

## Key Data Structures

### SQLite tables (arena.db)

| Table | Purpose |
|-------|---------|
| `ratings` | ELO per model: model, elo, wins, losses, draws |
| `history` | Match log: model_a, model_b, category, elo deltas, ts |
| `task_detail` | Full per-task data: match_id, task_id, instruction, response_a, response_b, expected, score_a, score_b, outcome, tps, latency |
| `benchmark_runs` | Benchmark results: model, score (0–100), scores_by_category (JSON), n_tasks, ts |
| `perf_log` | TPS/latency/TTFT per generation |

### Task dict format

```python
{
    "id": "math_001",
    "difficulty": "easy",        # easy | medium | hard
    "category": "math",
    "instruction": "...",
    "expected_answer": "12",
    "check": "exact",            # exact | exact_prefix | contains | contains_all |
                                 # contains_any | numeric_approx
    # optional:
    "check_items": ["2", "3"],   # for contains_all / contains_any
    "tolerance": 1,              # for numeric_approx
    "use_judge": True,           # for creative tasks
    "judge_rubric": "...",
    "language": "python",        # for coding tasks
    "test_code": "...",          # for coding tasks (appended to model output, run in sandbox)
    "has_bug": True,             # for inspection tasks
    "expected_issues": [...],    # for inspection tasks
    "expected_vulns": [...],     # for security tasks
    "key_components": [...],     # for planning tasks
}
```

---

## Evaluator Routing (`evaluator.py`)

```python
def evaluate(task, response) -> float:  # returns 0.0–1.0
    cat = task["category"]
    if cat == "coding":          → eval_coding()   # runs code + test in sandbox
    if cat in ("math", "reasoning", "knowledge"): → eval_text_answer()
    if cat == "security":        → eval_security()
    if cat == "inspection":      → eval_inspection()
    if cat == "planning":        → eval_planning()
    if cat == "creative":        → 0.5  # fallback; real score comes from LLMJudge
```

`eval_text_answer` supports check types: `exact`, `exact_prefix`, `contains`, `contains_all`, `contains_any`, `numeric_approx` (with `tolerance`).

`eval_inspection` uses 24 "clean code" phrase synonyms (not just 6). Detects both positive signals and absence of bug-words.

---

## CLI Commands

```bash
# Core
ollama-arena match --models llama3.2:3b,qwen2.5-coder:7b --category coding -n 10
ollama-arena match --models A,B --share          # prints shareable markdown table
ollama-arena match --models A,B --verbose        # prints full prompt + responses live

# Benchmark (Score 0–100 across 7 categories × 6 tasks)
ollama-arena benchmark llama3.2:3b
ollama-arena benchmark A,B --compare             # side-by-side
ollama-arena benchmark llama3.2:3b --fail-below 65   # exit 1 if below threshold (CI)

# Results & analysis
ollama-arena results                  # list recent matches
ollama-arena results --match 42       # drill into match #42 (all tasks + responses)
ollama-arena results --full           # untruncated responses
ollama-arena inspect math_005         # all runs for a specific task across all models
ollama-arena report llama3.2:3b       # per-category win rates + strength/weakness

# Discovery
ollama-arena leaderboard              # ELO rankings
ollama-arena tasks                    # list built-in tasks by category
ollama-arena list                     # alias for tasks

# Other
ollama-arena tournament --models A,B,C --category reasoning
ollama-arena web                      # FastAPI dashboard at localhost:7860
```

---

## Web Dashboard (`ollama-arena web`)

FastAPI server at `http://localhost:7860`. Six tabs:

| Tab | What it shows |
|-----|--------------|
| Dashboard | ELO leaderboard, ELO timeline, radar chart, heatmap, match history |
| Match | Configure and run matches live with streaming log |
| **Inspect** | Enter task ID → see all model responses side-by-side with scores |
| **Report** | Select model → per-category win rate table with strength/weakness verdict |
| Datasets | HuggingFace benchmark datasets (download + cache) |
| Performance | TPS/latency scatter plot + per-model perf table |

API endpoints: `/api/leaderboard`, `/api/history`, `/api/models`, `/api/categories`,
`/api/task/{task_id}`, `/api/report/{model}`, `/api/perf`, `/api/version`.

---

## Backends

```python
# Ollama (default)
Arena()
Arena(backend=OllamaBackend(host="http://localhost:11434"))

# OpenAI-compatible (vLLM, LM Studio, llama.cpp, OpenAI, Groq, Together, OpenRouter)
Arena(backend=OpenAICompatBackend(base_url="http://localhost:1234/v1", api_key="..."))

# HuggingFace (in-process, needs [hf] extra)
Arena(backend=TransformersBackend(device="mps"))
```

---

## Important Implementation Notes

1. **ELO update is per-task, not per-match** — K=32, each task result updates ELO independently.
2. **Callback signature** — `on_task(tid, sa, sb, outcome, instruction="", resp_a="", resp_b="", expected="")` — web.py and cli.py both use 8-arg form.
3. **job_id in web.py** includes timestamp to avoid collision: `f"{ma}_vs_{mb}_{cat}_{n}_{int(time.time())}"`.
4. **Coding sandbox** — static deny-list blocks `os.system`, `subprocess`, `socket` etc.; Docker optional.
5. **creative tasks** always have `use_judge=True`; without a judge model they fall back to `0.5`.
6. **`--fail-below`** flag causes `benchmark` to `sys.exit(1)` — designed for CI quality gates.
7. **All math/knowledge tasks are offline** — no HuggingFace dependency; works immediately after install.

---

## What's Done vs. Pending

### Done (as of v2.4.0)
- [x] Multi-backend support (Ollama, OpenAI-compat, HuggingFace)
- [x] ELO arena with full response storage (`task_detail` table)
- [x] `results`, `inspect`, `report` commands
- [x] `benchmark` command — Score 0–100 across 7 categories
- [x] `--share` markdown output, `--verbose` live output, `--fail-below` CI gate
- [x] 229 built-in tasks across 8 categories (all offline except HF datasets)
- [x] Web UI with Inspect + Report tabs, dynamic categories, live version badge
- [x] FastAPI API endpoints: `/api/task/{id}`, `/api/report/{model}`, `/api/version`
- [x] GitHub Actions CI template (`examples/github_actions/llm-benchmark.yml`)
- [x] Published to PyPI as `ollama-arena` v2.4.0
- [x] `eval_inspection` — expanded to 24 clean-code synonyms
- [x] `contains_all` / `contains_any` check types in evaluator
- [x] Web Visual Arena (Pixel Game Visualizer) on HTML5 Canvas
- [x] Interactive A/B Human Playground (Blind Testing) with ELO updates

### Pending (Phase 3–4 from roadmap)
- [x] `ollama-arena publish` command — upload results to GitHub Gist
- [ ] Community leaderboard page (GitHub Pages)
- [x] MkDocs documentation site (`docs/` + `mkdocs.yml`)
- [ ] Demo GIF in README (record with `asciinema rec demo.cast`, convert with `agg`)
- [x] Expand coding tasks: +20 Python (`coding.py`), +16 multilang (`coding_multilang.py`)
- [ ] Announcements: Show HN + r/LocalLLaMA (after demo GIF is ready)

---

## Development

```bash
# Install in dev mode
pip install -e ".[web,viz,datasets,dev]"

# Run tests (21 smoke tests, all should pass)
pytest tests/ -q

# Start web UI
ollama-arena web

# Build for PyPI
python3 -m build && twine check dist/*
twine upload dist/*  # needs PYPI_API_TOKEN or ~/.pypirc
```

### GitHub Actions (CI publish)
Workflow at `.github/workflows/publish.yml` triggers on `v*.*.*` tags.
Requires `PYPI_API_TOKEN` secret in GitHub repository settings.
