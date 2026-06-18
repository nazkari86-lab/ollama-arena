# ollama-arena

**"Which of my local models is actually better at coding?"** — ollama-arena answers
that in 60 seconds. It runs pair-wise battles between local LLMs, scores each response
automatically, and keeps an ELO leaderboard across sessions.

```
pip install ollama-arena
ollama-arena benchmark llama3.2:3b,qwen2.5-coder:7b --compare
```

```
  llama3.2:3b         Score: 61.3 / 100   (coding:58  reasoning:65  security:70 ...)
  qwen2.5-coder:7b    Score: 74.8 / 100   (coding:82  reasoning:71  security:68 ...)
  Winner: qwen2.5-coder:7b  (margin: 13.5 pts)
```

Or run a detailed head-to-head with shareable output:

```
ollama-arena match --models llama3.2:3b,qwen2.5-coder:7b --category coding -n 10 --share
```

```
  ✓ A  code_001  1.00 vs 0.00  [easy][python]  Write a sieve of Eratosthenes…
  ✓ B  code_002  0.00 vs 1.00  [medium][python] Implement an LRU cache…
  = =  code_003  1.00 vs 1.00  [hard][python]   Write a consistent hash ring…
  ...

  rank  model                elo    W   L   D   win%
  1     qwen2.5-coder:7b    1271    7   1   2   70%
  2     llama3.2:3b         1129    1   7   2   10%
```

## Why

When you have several local models, you want a quick answer to "which one
is better at *X*?" — without renting GPUs or signing up for a judging API.
Existing harnesses (lm-evaluation-harness, lighteval, simple-evals) are
absolute-score frameworks designed for paper-grade reporting; they are
overkill for the day-to-day "should I switch from llama3.2 to qwen2.5?"
question. ollama-arena answers that question with pair-wise battles, a
local SQLite ELO table, and built-in or HuggingFace task pools.

ELO rather than Glicko-2 because (a) the implementation is two lines, and
(b) for a moderate number of models the difference is negligible.

## Install

```
pip install ollama-arena
```

Optional extras:

| Extra | Adds |
|---|---|
| `pip install 'ollama-arena[wasm]'` | WASM sandbox fallback when Docker is unavailable |
| `pip install 'ollama-arena[all]'` | web dashboard, Plotly charts, HuggingFace datasets |
| `pip install 'ollama-arena[hf]'` | in-process TransformersBackend (torch, transformers) |
| `pip install 'ollama-arena[finetune]'` | Unsloth fine-tune pipeline — CUDA recommended |

The HuggingFace and fine-tune extras pull large dependencies and are off by default.

## Quick Start Guide

### For Different Use Cases

**Quick Model Comparison:**
```bash
ollama-arena benchmark llama3.2:3b,qwen2.5-coder:7b --compare
```

**Detailed Head-to-Head Analysis:**
```bash
ollama-arena match --models llama3.2:3b,qwen2.5-coder:7b --category coding -n 10 --verbose
```

**Multi-Model Tournament:**
```bash
ollama-arena tournament --models llama3.2:3b,qwen2.5-coder:7b,mistral:7b --category reasoning -n 5
```

**Using Custom Datasets:**
```bash
ollama-arena datasets --pull humaneval,gsm8k
ollama-arena match --dataset humaneval --models A,B -n 50
```

### Troubleshooting Common Issues

**Connection Issues:**
- Ensure Ollama is running: `ollama serve`
- Check default URL: `http://localhost:11434`
- Use custom URL: `ollama-arena --backend http://your-server:port match ...`

**Memory Issues:**
- Use memory scheduler: `ollama-arena match --memory-mode hot_swap ...`
- Limit concurrent models: `ollama-arena match --max-concurrent 1 ...`

**Docker Sandbox Issues:**
- Check Docker is running: `docker ps`
- Fall back to WASM: `pip install 'ollama-arena[wasm]'`

**Import Errors:**
- Ensure Python 3.9+: `python --version`
- Reinstall package: `pip install --force-reinstall ollama-arena`

## Quick start

```
ollama serve
ollama pull llama3.2:3b
ollama pull qwen2.5-coder:7b

ollama-arena match --models llama3.2:3b,qwen2.5-coder:7b --category coding -n 10
ollama-arena leaderboard
```

ELO state lives in `arena.db` in the working directory. Pass `--db` to
share a leaderboard between runs in different folders.

## Backends

Anything that exposes Ollama's native API or the OpenAI
`/v1/chat/completions` shape works without code changes:

```
ollama-arena --backend ollama   match ...        # default, :11434
ollama-arena --backend vllm     match ...        # :8000
ollama-arena --backend lmstudio match ...        # :1234
ollama-arena --backend llamacpp match ...        # :8080
ollama-arena --backend openai     --api-key sk-... match ...
ollama-arena --backend groq       --api-key gsk-... match ...
ollama-arena --backend together   --api-key tg-... match ...
ollama-arena --backend openrouter --api-key sk-or-... match ...
```

Or pass a full URL:

```
ollama-arena --backend http://192.168.1.50:8000/v1 match ...
```

A `TransformersBackend` is also available for in-process generation via
PyTorch; it is lazily imported so the dependency is optional.

## Tasks

The package ships with **286 hand-written tasks** across five
categories: coding (Python plus JS/TS/Rust/Go/C++), reasoning, security,
inspection, and planning. They are intended as a smoke-test starter pack,
not a definitive benchmark.

For serious work, load a HuggingFace dataset:

```
ollama-arena datasets                       # registered datasets
ollama-arena datasets --pull humaneval,gsm8k
ollama-arena match --dataset humaneval --models A,B -n 50
```

Registered loaders (more in `ollama_arena/datasets/loader.py`):

| name        | source            | reference                                     |
| ----------- | ----------------- | --------------------------------------------- |
| humaneval   | openai_humaneval  | Chen et al., 2021                             |
| mbpp        | mbpp              | Austin et al., 2021                           |
| mbpp_plus   | evalplus/mbppplus | Liu et al., 2023                              |
| gsm8k       | gsm8k             | Cobbe et al., 2021                            |
| mmlu        | cais/mmlu         | Hendrycks et al., 2021                        |
| bbh         | lukaemon/bbh      | Suzgun et al., 2022                           |
| multipl_e   | nuprl/MultiPL-E   | Cassano et al., 2022                          |
| hellaswag   | hellaswag         | Zellers et al., 2019                          |
| truthfulqa  | truthful_qa       | Lin et al., 2022                              |
| arc         | ai2_arc           | Clark et al., 2018                            |

Downloads are cached in `~/.cache/ollama_arena/datasets/`. Override with
`OLLAMA_ARENA_CACHE`.

## Scoring

Each task carries its own scorer:

- **coding** — extract the code block, append the task's test cases, and
  execute in the matching language sandbox. Score is 1.0 on a clean exit,
  0.0 otherwise.
- **math, knowledge** — numeric tolerance / multiple-choice letter match.
- **reasoning** — prefix or substring match against `expected_answer`.
- **security, inspection, planning** — keyword presence over an expected
  set of issues / key components.
- **open-ended** — when `task["use_judge"]` is set and the arena is
  constructed with `judge_model=...`, the LLMJudge grades each pair in
  both orderings (A then B, B then A) and averages, to suppress position
  bias. This is meaningfully more expensive — the judge is invoked twice
  per task, on top of the two model generations.

Code is executed in a subprocess with a hardened pattern filter
(`rm -rf`, `shell=True`, raw sockets, …) and a strict timeout. For
untrusted code, pass `use_docker=True` to `run_in_language()`; containers
run with `--network=none --read-only --memory=512m --cpus=1`.

## Languages

The sandbox dispatches by the `language` field on each task. Detected at
runtime from `$PATH`:

| language    | runtime needed                       |
| ----------- | ------------------------------------ |
| python      | python3                              |
| javascript  | node                                 |
| typescript  | tsx, ts-node, or deno                |
| rust        | rustc (edition 2021)                 |
| go          | go ≥ 1.20                            |
| cpp         | g++ or clang++ (-std=c++17)          |
| bash        | bash                                 |

`ollama-arena tasks` shows which languages are currently runnable.

## CI / GitHub Actions

Use ollama-arena as a quality gate in CI. Add to `.github/workflows/`:

```yaml
- run: pip install ollama-arena
- run: ollama-arena benchmark ${{ vars.LLM_MODEL }} --fail-below 65
- run: ollama-arena match --models ${{ vars.MODEL_A }},${{ vars.MODEL_B }} --share >> $GITHUB_STEP_SUMMARY
```

A full template is in [`examples/github_actions/llm-benchmark.yml`](examples/github_actions/llm-benchmark.yml).

## CLI

```
ollama-arena benchmark    MODEL[,MODEL2]  [--compare] [--fail-below SCORE]
ollama-arena match        --models A,B [--category C] [--dataset NAME] [--verbose] [--share]
ollama-arena tournament   --models A,B,C,...
ollama-arena leaderboard
ollama-arena results                          # list recent matches
ollama-arena results      --match <ID>        # all tasks from match #ID
ollama-arena results      --match <ID> --full # full untruncated responses
ollama-arena inspect      <TASK_ID>           # every run for one task
ollama-arena inspect      <TASK_ID> --full    # with complete responses
ollama-arena report                           # per-model category breakdown
ollama-arena report       --model llama3      # filter to one model
ollama-arena perf
ollama-arena list
ollama-arena tasks
ollama-arena datasets     [--pull NAMES] [--refresh NAMES]
ollama-arena finetune     --analyze | --generate | --train PATH
ollama-arena export       --out report.html
ollama-arena council       --models A,B,C --topic "Architecture debate"
ollama-arena resolve-issue --model X --issue "Fix the parser bug"
ollama-arena optimize-prompt --model X
ollama-arena review-pr     --models A,B
ollama-arena import        --file data.csv
ollama-arena web          [--port 7860]
```

Global flags: `--backend`, `--api-key`, `--db`, `--ollama`.

Every task result — the prompt sent to each model, both responses, the
expected answer, and the score — is stored in `arena.db`. Commands `results`,
`inspect`, and `report` query that history so you can audit exactly what the
models said and why they passed or failed.

## Python

```python
from ollama_arena import Arena

arena = Arena()                                      # Ollama on :11434
# arena = Arena(backend="vllm")
# arena = Arena(backend="groq", api_key="gsk_...")

arena.load_hf_dataset("humaneval", limit=50)

result = arena.run_match(
    "llama3.2:3b", "qwen2.5-coder:7b",
    category="coding", n=20,
)
print(result.elo_a_after, result.elo_b_after)
```

Round-robin between several models:

```python
arena.run_tournament(
    ["llama3.2:3b", "qwen2.5-coder:7b", "gemma2:9b"],
    category="reasoning", n_per_match=10,
)
```

LLM judge for open-ended responses:

```python
arena = Arena(judge_model="qwen2.5:32b-instruct")
# tasks marked {"use_judge": True} are graded by the judge in both orderings
```

Export a standalone HTML dashboard (Plotly):

```python
from ollama_arena.visualize import export_dashboard

export_dashboard(
    "report.html",
    leaderboard=arena.leaderboard(),
    matches=arena.match_history(limit=500),
    categories=["coding", "reasoning", "security", "planning", "inspection"],
    performance=arena.performance_stats(),
)
```

## Performance metrics

Every generation logs prompt tokens, output tokens, latency, tokens/sec,
and time-to-first-token. `ollama-arena perf` prints per-model
aggregates:

```
model              samples  tps mean  tps p95  lat mean  lat p95  ttft
llama3.2:3b           120     48.2     52.1     4.2s     6.3s    0.3s
qwen2.5-coder:7b      120     31.7     34.0     8.1s    11.2s    0.5s
```

These numbers are *backend* numbers — they include HTTP overhead, the
model server's scheduling, batching, and so on. They are useful as
relative comparisons within one backend; treat absolute values with care.

## Fine-tuning loop

A small pipeline turns arena failures into a teacher-distilled SFT
dataset, runs Unsloth LoRA on it, exports a GGUF and registers the
result as an Ollama model. End-to-end example:
[`examples/finetune_pipeline.py`](examples/finetune_pipeline.py).

CUDA is required for the Unsloth step.

## Limitations

- ELO updates per task, not per match. This converges faster but is
  noisier than the official chess formula for small sample sizes.
- The keyword-based scorers for security/inspection/planning are
  approximate. They reward mentioning the right thing, not necessarily
  understanding it. Use the LLM judge for higher-stakes scoring.
- Sandbox isolation without Docker relies on the subprocess timeout and
  the static pattern filter. Do not feed model output from untrusted
  sources to the host sandbox.
- HuggingFace dataset normalization is per-loader; some upstream schema
  changes will require updates to `loader.py`.

## Contributing

See `CONTRIBUTING.md`. The most useful contributions are new dataset
loaders, new language sandboxes, and new backends; each takes only a few
dozen lines.

## License

MIT. See `LICENSE`.

<details>
<summary>Logo</summary>

```
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣀⣀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⡠⢄⡲⠖⠛⠉⠉⠉⠉⠉⠙⠛⠿⣿⣶⣦⣄⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⠔⣡⠖⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣿⣿⣿⣿⣷⣦⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⠔⣡⠞⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⡔⢡⣶⠏⠀⠀⠀⠀⠀⠀⣠⣴⣶⣶⣶⣶⣶⣶⣦⣄⣸⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⠌⢀⣿⠏⠀⠀⠀⠀⠀⠀⠸⠿⠋⠙⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⡞⠀⡼⢿⣦⣄⠠⠤⠐⠒⠒⠒⠢⠤⣄⣠⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣸⠀⠀⠀⣸⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠻⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⢠⠞⠁⠀⠀⠠⠇⣀⣀⣀⣀⣀⠀⠀⠀⠀⠀⠀⠀⠀⢀⠈⠙⠛⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⢀⣴⣁⠀⣀⣤⣴⣾⣿⣿⣿⣿⡿⢿⣿⣶⣄⠀⠀⠀⠀⠀⣿⣷⠀⠀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⣿⣿⡇⠀⢸⣿⣿⣿⡇⠘⠟⣻⣿⣧⠀⠀⠀⠀⢿⣿⣤⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⣿⣿⣿⣿⣿⡿⠀⠀⠸⣿⠿⠋⠉⠁⠛⠻⠿⢿⣧⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⣿⣿⣿⡿⠋⠁⠀⢀⣄⡀⠀⠀⠀⢀⣀⣤⣴⣿⣿⣧⠀⢀⠀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣇⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⣿⣿⠏⢀⠀⢀⡴⠿⣿⣿⣷⣶⣾⣿⣿⣿⣿⣿⣿⣿⣇⠀⢷⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⣿⣿⣤⣿⣷⡈⠀⠀⠀⠙⠻⣿⣿⣿⣿⠿⠛⠛⣻⣿⣿⡄⠈⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣄⠀⠀⠀⠀⠈⠋⢉⣠⣴⣾⣿⣿⣿⣿⣷⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⡀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⢸⣿⣿⢻⡏⢹⠙⡆⠀⠀⠀⠒⠚⢛⣉⣉⣿⣿⣿⣿⣿⣿⡇⠀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⡀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⢀⡞⠁⠉⠀⠁⠀⣄⣀⣠⣴⣶⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣤⣈⡛⢻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⡀⠀⠀⠀⠀
⠀⠀⠀⠀⠛⠋⠉⠉⠉⠙⠻⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⡀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠙⠻⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡷⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠉⣻⠿⠿⢿⣿⠿⠿⠋⠁⠀⠙⣿⡁⠈⠻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡟⠛⠋⠉⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣠⠴⠞⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣈⣹⣦⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣤⡀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⢀⣀⣀⣀⣀⣀⣀⣀⣀⣼⣿⣄⣀⣀⡄⠀⣀⣀⣠⣤⣶⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⡀⠀⠀
⠀⠀⠀⠀⠀⢰⠿⠿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟⠉⠀⠀⣰⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⡀
⠀⠀⠀⢀⣤⣤⣤⣶⣿⣿⣿⣿⠿⠿⠟⠋⢹⠇⠀⠀⢀⣼⣿⣿⣿⣿⣿⡿⠻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇
⠀⢀⣴⣿⣿⣿⣿⣿⣿⣿⡟⠁⠀⠀⠀⢀⡏⠀⠀⢀⣾⠋⣹⣿⣿⣿⡟⠀⠀⣸⡟⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇
⢠⣿⣿⣿⣿⣿⣿⣿⣿⡟⠀⠀⠀⠀⠀⡼⠀⠀⢀⣾⠏⢀⣿⣿⣿⠋⠀⠀⣰⣿⣧⡀⠹⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇
```

</details>
