# ⚔️ Ollama Arena

**The local LLM ELO arena.** Battle your Ollama / vLLM / LM Studio / llama.cpp / OpenAI-compat models against each other on **real HuggingFace benchmarks** — HumanEval, MBPP, GSM8K, MMLU, MultiPL-E — with **multi-language code execution** (Python, JS, Rust, Go, TS, C++), **automatic ELO ratings**, **Plotly dashboards**, and a **closed-loop Unsloth fine-tune pipeline** that finds your model's weak spots and trains them away.

<p align="center">
  <img src="https://img.shields.io/pypi/v/ollama-arena?color=58a6ff" />
  <img src="https://img.shields.io/pypi/pyversions/ollama-arena?color=58a6ff" />
  <img src="https://img.shields.io/github/license/nazkari86-lab/ollama-arena?color=58a6ff" />
  <img src="https://img.shields.io/github/stars/nazkari86-lab/ollama-arena?style=social" />
</p>

```bash
pip install ollama-arena
ollama-arena match --models llama3.2:3b,qwen2.5-coder:7b,gemma2:9b --category coding -n 20
```

```
⚔️  OLLAMA ARENA — Backend: ollama
Models: llama3.2:3b, qwen2.5-coder:7b, gemma2:9b
Category: coding  |  Tasks per match: 20

Match 1/3: llama3.2:3b vs qwen2.5-coder:7b
  ✅ humaneval_1: 1.00 (38tps) vs 1.00 (51tps)
  ❌ humaneval_5: 0.00 (42tps) vs 1.00 (49tps)
  ✅ code_js_001: 1.00 (40tps) vs 1.00 (52tps)
  ...

🏆 ELO Leaderboard
╔══════╦════════════════════════╦═════════╦════╦════╦═══════╦══════╗
║ Rank ║ Model                  ║   ELO   ║ W  ║ L  ║ Mtch  ║ Win% ║
╠══════╬════════════════════════╬═════════╬════╬════╬═══════╬══════╣
║  🥇  ║ qwen2.5-coder:7b       ║  1287.4 ║ 47 ║ 13 ║   60  ║  78% ║
║  🥈  ║ gemma2:9b              ║  1218.6 ║ 32 ║ 28 ║   60  ║  53% ║
║  🥉  ║ llama3.2:3b            ║  1094.0 ║ 17 ║ 43 ║   60  ║  28% ║
╚══════╩════════════════════════╩═════════╩════╩════╩═══════╩══════╝
```

---

## ✨ What's new in v2.0

| Feature | What it does |
|---|---|
| 🔌 **Multi-backend** | Works with Ollama, vLLM, LM Studio, llama.cpp, OpenAI, Groq, Together, OpenRouter, Fireworks, DeepInfra — anything that speaks OpenAI's `/v1/chat/completions` |
| 📚 **HuggingFace datasets** | One-line pull of HumanEval (164), MBPP, MBPP+, GSM8K (8.5K), MMLU (14K, 57 subjects), BBH, MultiPL-E, TruthfulQA, HellaSwag, ARC |
| 🌐 **Multi-language code** | Auto-executes generated code in Python, JavaScript, TypeScript, Rust, Go, C++, Bash with strict sandboxing |
| 📊 **Plotly dashboard** | Live web UI on `:7860` with ELO timeline, capability radar, head-to-head heatmap, performance charts |
| ⚡ **Performance tracking** | Tokens/sec mean+p95, latency p95, time-to-first-token for every model |
| 🧠 **Unsloth fine-tune loop** | Analyze weak categories → generate teacher data from your strongest model → LoRA train → export GGUF → re-install in Ollama → re-benchmark |
| 🐳 **Docker sandbox mode** | Optional `--use-docker` for fully isolated code execution |
| 📤 **Shareable HTML export** | `ollama-arena export` produces a self-contained dashboard.html with embedded charts |

---

## 🧪 Why this exists

You have 10 local LLMs and no idea which is actually best at *your* tasks. Cloud arenas like LMSYS only rank API models.  Existing harnesses (lm-eval-harness, LightEval) are great for paper-grade evaluation — but they need PhD-level configuration to compare *the models running on your laptop*.

`ollama-arena` is the **5-minute** answer: one `pip install`, one command, beautiful results.

---

## 🚀 Quick Start

### 1. Install

```bash
pip install ollama-arena            # core
pip install 'ollama-arena[all]'     # +web +viz +datasets
pip install 'ollama-arena[finetune]'  # +unsloth (CUDA recommended)
```

### 2. Start your backend

```bash
ollama serve                                      # default: :11434
# or
vllm serve mistralai/Mistral-7B-Instruct --port 8000
# or
lms server start                                  # LM Studio, :1234
```

### 3. Fight

```bash
ollama-arena match --models llama3.2,qwen2.5:7b --category coding -n 10
ollama-arena leaderboard
```

### 4. Browse

```bash
ollama-arena web                                  # http://localhost:7860
```

---

## 🔌 Backends

```bash
# Ollama (default)
ollama-arena match --models llama3.2,gemma2 ...

# vLLM (OpenAI-compatible)
ollama-arena --backend http://localhost:8000/v1 match --models mistral,phi3 ...

# LM Studio
ollama-arena --backend lmstudio match --models any-gguf,another ...

# llama.cpp server
ollama-arena --backend llamacpp match --models any ...

# Cloud (Groq, OpenAI, Together, OpenRouter, ...)
ollama-arena --backend groq --api-key gsk_... match --models llama-3.1-70b-versatile,mixtral-8x7b ...
```

Mix and match — every match goes into the same SQLite, so you get a **unified ELO leaderboard** across all backends.

---

## 📚 HuggingFace Benchmark Datasets

```bash
# Browse available datasets
ollama-arena datasets

# Pull HumanEval (Python code generation, 164 tasks)
ollama-arena datasets --pull humaneval

# Pull multiple at once
ollama-arena datasets --pull humaneval,mbpp,gsm8k,mmlu

# Use them in a match
ollama-arena match --dataset humaneval --models llama3.2,qwen2.5-coder -n 30
```

| Dataset | HF id | Category | Use case |
|---|---|---|---|
| `humaneval` | `openai_humaneval` | coding | Python code generation (164 tasks) |
| `mbpp` | `mbpp` | coding | Mostly Basic Python Problems |
| `mbpp_plus` | `evalplus/mbppplus` | coding | MBPP+ with extended tests |
| `gsm8k` | `gsm8k` | math | Grade-school math word problems (8.5K) |
| `mmlu` | `cais/mmlu` | knowledge | 57 subjects, multiple choice |
| `bbh` | `lukaemon/bbh` | reasoning | Big-Bench Hard |
| `multipl_e` | `nuprl/MultiPL-E` | coding | HumanEval in 22 languages |
| `truthfulqa` | `truthful_qa` | knowledge | Factual honesty |
| `hellaswag` | `hellaswag` | reasoning | Common-sense reasoning |
| `arc` | `ai2_arc` | knowledge | Science questions |

Datasets cache under `~/.cache/ollama_arena/datasets/`.

---

## 🌐 Multi-language code execution

The arena auto-runs whatever the model produced — in the right language.

```bash
ollama-arena tasks       # see built-in tasks per language
```

```
Languages covered: cpp, go, javascript, python, rust, typescript
```

Auto-detected runtimes:

| Language | Runtime |
|---|---|
| Python | `python3` |
| JavaScript | `node` |
| TypeScript | `tsx` / `ts-node` / `deno` |
| Rust | `rustc` |
| Go | `go run` |
| C++ | `g++` or `clang++` |
| Bash | `bash` |

Want stronger isolation? Pass `use_docker=True` to `run_in_language()` — each language gets its own minimal container with `--network=none --read-only --memory=512m`.

---

## 📊 Web Dashboard

```bash
pip install 'ollama-arena[web,viz]'
ollama-arena web
```

Live at **http://localhost:7860** — tabs:

- **📊 Dashboard** — ELO leaderboard + timeline chart + capability radar + head-to-head heatmap
- **⚔️ Battle** — kick off matches from the browser, watch task-by-task results stream
- **📚 Datasets** — pull HuggingFace benchmarks with one click
- **⚡ Performance** — tokens/sec, latency p95, time-to-first-token per model

Or export a static, shareable HTML report:

```bash
ollama-arena export --out my_leaderboard.html
# Drop into Slack / Discord / GitHub release notes
```

---

## 🧠 Closed-loop fine-tune pipeline

The killer feature: turn arena losses into training data, then **fix your model**.

```python
from ollama_arena import Arena
from ollama_arena.finetune import (
    analyze_weaknesses, build_training_dataset, save_jsonl,
    unsloth_train, UnslothConfig,
    build_modelfile, install_to_ollama,
)

# 1. Baseline benchmark
arena = Arena()
arena.run_tournament(["llama3.2:3b", "qwen2.5-coder:7b"], category="coding", n_per_match=20)

# 2. Find weakest (model, category) pair
weak = analyze_weaknesses("arena.db")[0]
print(weak)   # {'model': 'llama3.2:3b', 'category': 'coding', 'win_rate': 0.21, ...}

# 3. Generate teacher data: ask the strongest model to solve tasks the weak one failed
dataset = build_training_dataset(weak["model"], weak["category"], n_tasks=100)
jsonl = save_jsonl(dataset, "train.jsonl")

# 4. Unsloth LoRA fine-tune → GGUF
art = unsloth_train(jsonl, UnslothConfig(
    base_model="unsloth/llama-3.2-3b-instruct-bnb-4bit",
    epochs=2, save_gguf=True,
))

# 5. Install into Ollama
build_modelfile(art["gguf_path"], "Modelfile")
install_to_ollama("Modelfile", "llama3.2:3b-tuned")

# 6. Re-benchmark
arena.run_match("llama3.2:3b-tuned", "qwen2.5-coder:7b", category="coding", n=20)
arena.leaderboard()
```

Or use the CLI:

```bash
# 1. See your weak spots
ollama-arena finetune --analyze

# 2. Generate teacher data
ollama-arena finetune --generate --model llama3.2:3b --category coding --teacher qwen2.5-coder:7b

# 3. Train
ollama-arena finetune --train train.jsonl --epochs 2
```

---

## ⚡ Performance metrics

Every generation logs tokens-in, tokens-out, latency, tokens/sec, and time-to-first-token.

```bash
ollama-arena perf
```

```
⚡ Performance
╔════════════════════════╦══════════╦══════════╦══════════╦══════════════╦═════════════╦══════════╗
║ Model                  ║ Samples  ║ TPS mean ║ TPS p95  ║ Latency mean ║ Latency p95 ║ TTFT     ║
╠════════════════════════╬══════════╬══════════╬══════════╬══════════════╬═════════════╬══════════╣
║ llama3.2:3b            ║     120  ║   48.2   ║   52.1   ║      4.2s    ║     6.3s    ║   0.3s   ║
║ qwen2.5-coder:7b       ║     120  ║   31.7   ║   34.0   ║      8.1s    ║    11.2s    ║   0.5s   ║
║ gemma2:9b              ║     120  ║   24.5   ║   26.8   ║     11.4s    ║    14.7s    ║   0.7s   ║
╚════════════════════════╩══════════╩══════════╩══════════╩══════════════╩═════════════╩══════════╝
```

---

## 🧩 Python API

```python
from ollama_arena import Arena

# Multi-backend, auto-detection
arena = Arena()                                            # Ollama
arena = Arena(backend="http://localhost:8000/v1")          # vLLM
arena = Arena(backend="lmstudio")                          # LM Studio
arena = Arena(backend="groq", api_key="gsk_...")           # Groq cloud

# Use real benchmarks
arena.load_hf_dataset("humaneval", limit=50)
arena.load_hf_dataset("gsm8k",     limit=50)

# Run match
result = arena.run_match("llama3.2:3b", "qwen2.5-coder:7b",
                         category="coding", n=20)
print(f"Winner ELO: {result.elo_a_after:.0f} vs {result.elo_b_after:.0f}")
print(f"TPS: {result.task_results[0]['tps_a']} vs {result.task_results[0]['tps_b']}")

# Round-robin
arena.run_tournament(
    models=["llama3.2:3b", "qwen2.5-coder:7b", "gemma2:9b"],
    category="reasoning", n_per_match=10,
)

# Visualize
from ollama_arena.visualize import export_dashboard
export_dashboard(
    "report.html",
    leaderboard=arena.leaderboard(),
    matches=arena.match_history(limit=500),
    categories=["coding","reasoning","security","planning","inspection"],
    performance=arena.performance_stats(),
)
```

---

## 🛡️ Sandbox safety

Generated code is filtered against a hardened pattern list (`rm -rf`, `shell=True`, raw socket access, `child_process`, `urllib.request`, etc.) and executed under a strict subprocess timeout. For **untrusted production use**, pass `use_docker=True`:

```python
from ollama_arena.sandboxes import run_in_language
r = run_in_language("print(2+2)", language="python", use_docker=True)
```

Containers run with `--network=none --read-only --tmpfs=/tmp:rw,size=64m --memory=512m --cpus=1`.

---

## 📊 What's measured

### 5 task categories × 6 languages × 10 HF datasets

| Built-in | Tasks | HuggingFace | Tasks (after pull) |
|---|---:|---|---:|
| coding (Python+5 langs) | 44 | humaneval, mbpp, mbpp+, multipl_e | ~600 |
| reasoning | 15 | bbh, hellaswag | ~600 |
| security (CVE detect) | 15 | — | — |
| planning | 20 | — | — |
| inspection (bug-find) | 20 | — | — |
| math | (HF only) | gsm8k | 8.5K |
| knowledge | (HF only) | mmlu, truthfulqa, arc | ~15K |

### Auto-scoring

| Category | How |
|---|---|
| coding | Execute generated code, run assert tests, 0.0 / 1.0 |
| reasoning, math, knowledge | Exact match / numeric tolerance / prefix |
| security | Detect expected CWE class + severity (keyword) |
| inspection | Precision/recall of bug callouts |
| planning | Key-component coverage + length heuristic |

---

## 🛠️ Commands

```
ollama-arena match        --models A,B [--category coding] [--dataset humaneval]
ollama-arena tournament   --models A,B,C,D [--category coding]
ollama-arena leaderboard
ollama-arena list                                  # available models
ollama-arena tasks                                 # built-in benchmarks
ollama-arena datasets [--pull NAME] [--refresh]    # HF dataset cache
ollama-arena finetune --analyze | --generate | --train PATH
ollama-arena perf                                  # tokens/sec stats
ollama-arena export --out report.html              # shareable dashboard
ollama-arena web                                   # browser UI :7860

Global:
  --backend URL|PRESET    ollama, vllm, lmstudio, openai, groq, together, openrouter, ...
  --api-key  KEY
  --db       arena.db
```

---

## 🤝 Contributing

```bash
git clone https://github.com/nazkari86-lab/ollama-arena
cd ollama-arena
pip install -e ".[dev,all]"
pytest -q
```

PRs especially welcome for:

- 🆕 New HF datasets (add a normalizer in `datasets/loader.py`)
- 🌐 New language sandboxes (add a `_run_*` in `sandboxes/runner.py`)
- 🔌 New backend (add a `Backend` subclass in `backends/`)
- 📋 New tasks (drop into `tasks/`)

---

## 🗺️ Roadmap

- [x] Multi-backend (Ollama, vLLM, LM Studio, OpenAI-compat)
- [x] HuggingFace dataset loaders (10 datasets)
- [x] Multi-language sandbox (Python, JS, TS, Rust, Go, C++, Bash)
- [x] Plotly dashboard + radar + heatmap + ELO timeline
- [x] Performance metrics (tokens/sec, latency p95, TTFT)
- [x] Unsloth LoRA fine-tune loop with GGUF→Ollama install
- [x] Docker sandbox mode
- [ ] vLLM direct Python API backend (skip HTTP)
- [ ] HF Transformers direct backend
- [ ] HF Spaces template (share a leaderboard publicly)
- [ ] OpenAI Evals format import
- [ ] Cost estimator (for cloud backends)

---

## 📄 License

MIT. Use freely, attribution appreciated.

---

<p align="center">
  <strong>Built for the local-LLM community. Star ⭐ if it saved you time.</strong>
</p>
