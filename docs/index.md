# ollama-arena

Pair-wise ELO evaluation arena for local LLMs (Ollama, vLLM, LM Studio, OpenAI-compatible APIs).

`ollama-arena` runs head-to-head battles between LLMs on built-in offline tasks, updates their ELO ratings, and aggregates benchmarks and performance statistics (TPS, latency, TTFT).

## Installation

Install via pip:

```bash
pip install ollama-arena
```

Or install with all extras:

```bash
pip install "ollama-arena[all]"
```

## Quick Start

1. Start your Ollama server or any other OpenAI-compatible backend.
2. Run a 10-task match between two models:
   ```bash
   ollama-arena match --models llama3.2:3b,qwen2.5-coder:7b --category coding -n 10
   ```
3. View the ELO leaderboard:
   ```bash
   ollama-arena leaderboard
   ```
4. Start the interactive web dashboard:
   ```bash
   ollama-arena web
   ```
