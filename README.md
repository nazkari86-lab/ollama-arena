# Ollama Arena

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

A local LLM evaluation arena with ELO ratings. Runs head-to-head matches
between models served by Ollama, vLLM, LM Studio, llama.cpp, or any OpenAI-
compatible endpoint; scores responses against built-in tasks or HuggingFace
datasets (HumanEval, MBPP, GSM8K, MMLU, BBH, MultiPL-E, …); executes
generated code in Python, JavaScript, TypeScript, Rust, Go, or C++; tracks
throughput and latency; and provides a closed-loop fine-tuning pipeline
built on Unsloth.

[![tests](https://github.com/nazkari86-lab/ollama-arena/actions/workflows/test.yml/badge.svg)](https://github.com/nazkari86-lab/ollama-arena/actions/workflows/test.yml)
[![python](https://img.shields.io/badge/python-3.9%2B-blue)](https://pypi.org/project/ollama-arena/)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

## Installation

```bash
pip install ollama-arena
pip install 'ollama-arena[all]'        # +web +viz +datasets
pip install 'ollama-arena[finetune]'   # +unsloth (CUDA recommended)
pip install 'ollama-arena[hf]'         # +transformers backend
```

## Quickstart

```bash
ollama serve
ollama pull llama3.2:3b
ollama pull qwen2.5-coder:7b

ollama-arena match --models llama3.2:3b,qwen2.5-coder:7b --category coding -n 10
ollama-arena leaderboard
ollama-arena web         # http://localhost:7860
```

```
Match 1/1: llama3.2:3b vs qwen2.5-coder:7b
  code_001:  1.00 vs 1.00  draw
  code_002:  0.00 vs 1.00  b_wins
  code_003:  1.00 vs 1.00  draw
  ...

Rank   Model                  ELO     W   L   D   Matches  Win%
1      qwen2.5-coder:7b      1271     7   1   2     10      70%
2      llama3.2:3b           1129     1   7   2     10      10%
```

## Backends

A backend speaks to a single model server. Pass it via `--backend`:

| Preset       | URL                                    |
|--------------|----------------------------------------|
| `ollama`     | `http://localhost:11434` (default)     |
| `vllm`       | `http://localhost:8000/v1`             |
| `lmstudio`   | `http://localhost:1234/v1`             |
| `llamacpp`   | `http://localhost:8080/v1`             |
| `openai`     | `https://api.openai.com/v1`            |
| `groq`       | `https://api.groq.com/openai/v1`       |
| `together`   | `https://api.together.xyz/v1`          |
| `openrouter` | `https://openrouter.ai/api/v1`         |
| `deepinfra`  | `https://api.deepinfra.com/v1/openai`  |
| `fireworks`  | `https://api.fireworks.ai/inference/v1`|

```bash
ollama-arena --backend vllm     match --models mistral-7b,phi-3 ...
ollama-arena --backend lmstudio match --models any-local-gguf,another ...
ollama-arena --backend groq --api-key gsk_... match --models llama-3.1-70b,mixtral-8x7b ...
```

All matches share `arena.db`, so the leaderboard is unified across backends.

A native `transformers` backend is available for direct PyTorch inference
without HTTP:

```python
from ollama_arena.backends._lazy_transformers import _lazy_transformers
TransformersBackend = _lazy_transformers()
arena = Arena(backend=TransformersBackend(device="cuda"))
```

## HuggingFace datasets

```bash
ollama-arena datasets                          # list available
ollama-arena datasets --pull humaneval,gsm8k   # download & cache
ollama-arena match --dataset humaneval --models qwen2.5-coder,llama3.2 -n 50
```

| Name         | HF id                  | Category   | Tasks  |
|--------------|------------------------|------------|--------|
| humaneval    | openai_humaneval       | coding     | 164    |
| mbpp         | mbpp                   | coding     | 974    |
| mbpp_plus    | evalplus/mbppplus      | coding     | 378    |
| gsm8k        | gsm8k                  | math       | 1 319  |
| mmlu         | cais/mmlu              | knowledge  | 14 042 |
| bbh          | lukaemon/bbh           | reasoning  | 6 511  |
| multipl_e    | nuprl/MultiPL-E        | coding     | varies |
| truthfulqa   | truthful_qa            | knowledge  | 817    |
| hellaswag    | hellaswag              | reasoning  | 10 042 |
| arc          | ai2_arc                | knowledge  | 1 172  |

Datasets are cached under `~/.cache/ollama_arena/datasets/`.

## Languages

Generated code is executed in the language declared on the task. Runtimes
are auto-detected:

| Language    | Required runtime          |
|-------------|---------------------------|
| Python      | `python3`                 |
| JavaScript  | `node`                    |
| TypeScript  | `tsx` / `ts-node` / `deno`|
| Rust        | `rustc`                   |
| Go          | `go`                      |
| C++         | `g++` or `clang++`        |
| Bash        | `bash`                    |

For stronger isolation, pass `use_docker=True` to `run_in_language()`;
containers run with `--network=none --read-only --memory=512m --cpus=1`.

## CLI

```
ollama-arena match        --models A,B [--category C] [--dataset NAME] [--difficulty L]
ollama-arena tournament   --models A,B,C [--category C]
ollama-arena leaderboard
ollama-arena perf
ollama-arena list                                       # backend's models
ollama-arena tasks                                      # built-in benchmarks
ollama-arena datasets [--pull NAMES] [--refresh NAMES]
ollama-arena finetune --analyze | --generate | --train PATH
ollama-arena export   --out report.html
ollama-arena web      [--port 7860]
```

Global flags: `--backend URL|PRESET`, `--api-key`, `--db PATH`,
`--ollama URL`.

## Python API

```python
from ollama_arena import Arena

arena = Arena()                                     # Ollama on localhost
# arena = Arena(backend="vllm")                     # vLLM on :8000
# arena = Arena(backend="groq", api_key="gsk_...")  # cloud

arena.load_hf_dataset("humaneval", limit=50)

result = arena.run_match(
    "llama3.2:3b", "qwen2.5-coder:7b",
    category="coding", n=20,
)
print(result.elo_a_after, result.elo_b_after)

for entry in arena.leaderboard():
    print(entry["rank"], entry["model"], entry["elo"])
```

### Round-robin

```python
arena.run_tournament(
    ["llama3.2:3b", "qwen2.5-coder:7b", "gemma2:9b"],
    category="reasoning", n_per_match=10,
)
```

### LLM-as-judge for open-ended tasks

```python
arena = Arena(judge_model="qwen2.5:32b-instruct")
# Tasks marked {"use_judge": True} are scored by the judge instead of the
# deterministic evaluator. Each pair is graded in both orderings to mitigate
# position bias.
```

### Visualization

```python
from ollama_arena.visualize import export_dashboard

export_dashboard(
    "report.html",
    leaderboard  = arena.leaderboard(),
    matches      = arena.match_history(limit=500),
    categories   = ["coding", "reasoning", "security", "planning", "inspection"],
    performance  = arena.performance_stats(),
)
```

Standalone HTML containing ELO timeline, capability radar, head-to-head
heatmap, and throughput-vs-latency chart (Plotly).

## Performance metrics

Every generation logs prompt tokens, output tokens, latency, tokens/sec,
and time-to-first-token. View aggregates with `ollama-arena perf`:

```
Model              Samples  TPS mean  TPS p95  Lat mean  Lat p95  TTFT
llama3.2:3b           120     48.2     52.1      4.2s     6.3s    0.3s
qwen2.5-coder:7b      120     31.7     34.0      8.1s    11.2s    0.5s
gemma2:9b             120     24.5     26.8     11.4s    14.7s    0.7s
```

## Fine-tuning pipeline

```python
from ollama_arena import Arena
from ollama_arena.finetune import (
    analyze_weaknesses, build_training_dataset, save_jsonl,
    unsloth_train, UnslothConfig,
    build_modelfile, install_to_ollama,
)

weak = analyze_weaknesses("arena.db")
for w in weak[:5]:
    print(w["model"], w["category"], w["win_rate"])

# Pick the worst-performing pair
target = weak[0]
dataset = build_training_dataset(
    weak_model=target["model"], category=target["category"], n_tasks=100,
)
jsonl = save_jsonl(dataset, "train.jsonl")

artifacts = unsloth_train(jsonl, UnslothConfig(
    base_model="unsloth/llama-3.2-3b-instruct-bnb-4bit",
    epochs=2, save_gguf=True,
))

mf = build_modelfile(artifacts["gguf_path"])
install_to_ollama(mf, f"{target['model']}-tuned")
```

The student model is re-tested after install. Requires CUDA; see
`examples/finetune_pipeline.py`.

## Architecture

```
ollama_arena/
├── arena.py            Match driver
├── elo.py              ELO + SQLite store
├── performance.py      Throughput/latency tracker
├── evaluator.py        Deterministic graders (code exec, regex, etc.)
├── judge.py            LLM-as-judge for open-ended tasks
├── backends/
│   ├── ollama.py
│   ├── openai_compat.py     vLLM / LM Studio / llama.cpp / OpenAI-compat
│   └── transformers_backend.py
├── sandboxes/
│   └── runner.py            Python, JS, TS, Rust, Go, C++, Bash, Docker
├── datasets/
│   └── loader.py            HumanEval, MBPP, GSM8K, MMLU, BBH, MultiPL-E, …
├── visualize/
│   └── charts.py            Plotly fragments + standalone export
├── finetune/
│   ├── analyzer.py
│   ├── generator.py
│   ├── unsloth_runner.py
│   └── ollama_export.py
├── tasks/                   Built-in benchmark tasks
├── cli.py
└── web.py                   FastAPI dashboard
```

## Scoring

| Category    | Scoring                                                  |
|-------------|----------------------------------------------------------|
| coding      | Execute generated code + assert tests (0.0 / 1.0)        |
| math        | Numeric tolerance match                                  |
| reasoning   | Prefix / contains / exact match                          |
| knowledge   | Multiple-choice letter match                             |
| security    | Detection of expected CWE class + severity               |
| inspection  | Precision/recall over expected bug callouts              |
| planning    | Key-component coverage + length heuristic                |
| open-ended  | LLM-as-judge (when configured)                           |

## Safety

Generated code is filtered against a pattern list (`rm -rf`, `shell=True`,
raw socket access, etc.) before execution, then run under a strict
subprocess timeout. For untrusted inputs, use `use_docker=True`.

## Compatibility

- Python ≥ 3.9, OS-independent
- Tested on macOS and Ubuntu, CPython 3.10/3.11/3.12

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Particularly useful contributions:
new HuggingFace dataset loaders, new language sandboxes, new backends.

## License

[MIT](LICENSE)
