# Show HN: ollama-arena v2.5.0 - Local LLM Benchmark with Automatic Lineage Detection

Hi HN,

I'm excited to share ollama-arena v2.5.0, a local LLM evaluation tool that helps answer the question "which of my local models is actually better?" without needing cloud GPUs or paid APIs.

## What's new in v2.5.0

This release focuses on understanding model relationships with two major features:

### 1. Genome Lineage Auto-seed
- **Automatic lineage inference**: Heuristically detects model evolution relationships (fine-tuning, distillation, merging)
- **Smart pattern matching**: Analyzes naming conventions, architecture similarities, and parameter sizes
- **Confidence scoring**: Provides confidence levels for each inferred relationship
- **Command**: `ollama-arena genome auto-seed` to automatically build your model family tree

Example:
```bash
$ ollama-arena genome auto-seed --min-confidence 0.5

Lineage Hypotheses (3 found)
Child          | Parent         | Relation       | Confidence
---------------|----------------|----------------|------------
llama3.2:3b    | llama3.1:8b    | distilled_from | 0.65
qwen2.5-coder:7b| qwen2.5:7b    | fine_tuned_from| 0.85
```

### 2. Enhanced Genome Explorer
- **Expanded model registry**: Added 40+ canonical models with complete lineage data
- **Better visualization**: Improved tree structure for model evolution
- **Local model matching**: Automatically identifies your local models in the registry

## Core Features (from previous releases)

**Pairwise Battle System**: Run head-to-head matches between any local models
```bash
ollama-arena match --models llama3.2:3b,qwen2.5-coder:7b --category coding -n 10
```

**ELO Leaderboard**: Persistent rankings across sessions in SQLite
```bash
ollama-arena leaderboard
```

**Built-in Task Pool**: 286 hand-written tasks across coding, reasoning, security, planning
```bash
ollama-arena benchmark llama3.2:3b,qwen2.5-coder:7b --compare
```

**HuggingFace Integration**: Load serious benchmarks (HumanEval, GSM8K, MMLU, etc.)
```bash
ollama-arena datasets --pull humaneval,gsm8k
ollama-arena match --dataset humaneval --models A,B -n 50
```

**Multiple Backends**: Works with Ollama, vLLM, LM Studio, llama.cpp, OpenAI-compatible APIs

**Battle Royale Mode**: N-way simultaneous matches (3-8 models) with pairwise ELO updates

**Memory Scheduler**: Run large models on small RAM with hot-swap and pipeline modes

**Zero-Trust Sandbox**: AST-validated code execution in Docker/WASM

## Why I built it

When you have several local models, you want a quick answer to "which one is better at *X*?" without:
- Renting GPUs
- Signing up for judging APIs
- Running complex evaluation frameworks

Existing tools (lm-evaluation-harness, lighteval) are designed for paper-grade reporting and are overkill for day-to-day model comparison.

ollama-arena answers that question with:
- Pair-wise battles
- Local SQLite ELO table
- Built-in or HuggingFace task pools
- Simple CLI interface

## Tech Stack

- **Language**: Python 3.9+
- **Database**: SQLite for ELO and genome data
- **Sandbox**: Docker (default) with WASM/subprocess fallback
- **Scoring**: Automatic code execution, numeric tolerance, keyword matching
- **Visualization**: Rich CLI output + web dashboard with D3.js graphs
- **Dependencies**: Minimal (requests, rich, plotly for charts)

## Installation

```bash
pip install ollama-arena

# Optional extras
pip install 'ollama-arena[all]'  # web dashboard, charts, HF datasets
pip install 'ollama-arena[wasm]'  # WASM sandbox fallback
```

## Quick Start

```bash
ollama serve
ollama pull llama3.2:3b
ollama pull qwen2.5-coder:7b

# Compare models
ollama-arena benchmark llama3.2:3b,qwen2.5-coder:7b --compare

# Explore lineage
ollama-arena genome scan
ollama-arena genome auto-seed
ollama-arena genome tree

# View rankings
ollama-arena leaderboard
```

## Open Source

- GitHub: https://github.com/your-org/ollama-arena
- License: MIT
- PRs welcome!

I'd love feedback from the HN community, especially on:
1. The lineage inference algorithm - what heuristics work best?
2. Model registry coverage - what models should we add?
3. Task categories - what would you like to benchmark?

Thanks for checking it out!

---

**Note**: Requires Ollama (or compatible backend) running locally. See README for backend options (vLLM, LM Studio, llama.cpp, OpenAI-compatible APIs all work).
