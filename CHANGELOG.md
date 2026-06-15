# Changelog

## 2.0.0 — 2026-06-15

Major release — turns ollama-arena from a single-backend Ollama tool into a
universal local-LLM benchmarking platform.

### Added
- **Multi-backend support**: `OllamaBackend` + `OpenAICompatBackend` cover
  Ollama, vLLM, LM Studio, llama.cpp server, OpenAI, Groq, Together,
  OpenRouter, DeepInfra, Fireworks, and any `/v1/chat/completions` endpoint.
  Preset names: `vllm`, `lmstudio`, `llamacpp`, `openai`, `groq`, …
- **HuggingFace dataset integration** (`ollama_arena.datasets`):
  HumanEval, MBPP, MBPP+, GSM8K, MMLU, BBH, MultiPL-E, TruthfulQA,
  HellaSwag, ARC — all auto-normalized to the arena task schema.
- **Multi-language code execution** (`ollama_arena.sandboxes`):
  Python, JavaScript, TypeScript, Rust, Go, C++, Bash via native runtimes,
  plus optional Docker isolation (`use_docker=True`).
- **Plotly visualization** (`ollama_arena.visualize`):
  ELO timeline, capability radar, head-to-head heatmap, throughput-vs-latency.
  Self-contained shareable HTML via `export_dashboard()`.
- **Performance tracking** (`ollama_arena.performance.PerfTracker`):
  tokens/sec mean/p95, latency mean/p95, time-to-first-token.
- **Unsloth fine-tune loop** (`ollama_arena.finetune`):
  `analyze_weaknesses` → `build_training_dataset` → `unsloth_train` →
  `build_modelfile` → `install_to_ollama` → re-benchmark.
- **5 new multi-language coding tasks** in `tasks/coding_multilang.py`
  (JavaScript, TypeScript, Rust, Go, C++).
- New CLI subcommands: `tournament`, `datasets`, `finetune`, `perf`, `export`.
- New web dashboard with 4 tabs (Dashboard, Battle, Datasets, Performance)
  and live Plotly charts.
- GitHub Actions: tests (Ubuntu + macOS, py3.10–3.12) and PyPI publish.
- 17 pytest tests covering ELO, evaluator, sandbox, backends.

### Changed
- `Arena` now accepts a `backend=` argument (string preset, URL, or instance)
  and tracks per-generation performance metrics.
- `evaluator.py` routes coding tasks to the multi-language sandbox.
- Built-in coding category expanded with multi-language tasks.

### Compatibility
- `Arena(ollama_url=...)` and `OllamaClient` continue to work unchanged.
- New optional dependency groups: `[web]`, `[viz]`, `[datasets]`, `[finetune]`,
  `[all]`.

## 1.0.0 — 2026-06-15

Initial release: Ollama-only ELO arena with 100 hand-written tasks,
SQLite ELO store, Rich CLI, and basic FastAPI web UI.
