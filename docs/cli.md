# CLI Reference

`ollama-arena` features a robust command-line interface with several subcommands to run matches, view leaderboards, and manage your local LLM evaluations.

## General Options

```bash
ollama-arena [OPTIONS] COMMAND [ARGS]...
```

* `--ollama URL`: Ollama backend URL (default: `http://localhost:11434`)
* `--backend URL|PRESET`: Custom OpenAI-compatible backend endpoint or preset (e.g. `vllm`, `lmstudio`, `openai`)
* `--api-key KEY`: API key for custom backend if required
* `--db PATH`: Path to SQLite database containing ratings and match history (default: `arena.db`)

---

## Commands

### `match`

Pits models head-to-head in automated battles.

```bash
ollama-arena match --models A,B --category coding -n 10
```

**Options:**
* `--models A,B`: Comma-separated list of models to match.
* `--category`: Task category to select (`coding`, `reasoning`, `security`, `planning`, `inspection`, `math`, `knowledge`, `creative`, `all`).
* `-n INT`: Number of tasks to run in this match (default: 10).
* `--verbose, -v`: Prints the full prompt, expected answer, and both model responses in real-time.
* `--share`: Outputs a shareable markdown table summarizing the match results.

### `benchmark`

Evaluates a model's performance on a standardized suite of tasks, giving a score from 0 to 100.

```bash
ollama-arena benchmark llama3.2:3b
```

**Options:**
* `--compare`: Provides a side-by-side comparison if two models are specified.
* `--fail-below SCORE`: Exits with code 1 if any model scores below the given score (useful for CI/CD pipelines).

### `leaderboard` (or `lb`)

Shows the ELO rating standings of all models evaluated.

```bash
ollama-arena leaderboard
```

### `results`

Browse recent matches and inspect their per-task results.

```bash
ollama-arena results
ollama-arena results --match <ID>
```

**Options:**
* `--match ID`: Shows details and responses for the specific match ID.
* `--last INT`: Number of recent matches to list (default: 10).
* `--full`: Print complete, untruncated prompts and responses.

### `inspect`

Shows all recorded runs/answers for a specific task ID across all models.

```bash
ollama-arena inspect math_001
```

### `report`

Analyzes a model's strengths and weaknesses across all categories based on match history.

```bash
ollama-arena report --model llama3.2:3b
```

### `publish`

Uploads the current ELO leaderboard, recent matches, benchmark history, and performance stats to a GitHub Gist.

```bash
ollama-arena publish
```

**Options:**
* `--public`: Makes the created Gist public.
* *Note: Requires `GITHUB_TOKEN` or `GH_TOKEN` environment variable to be set.*
