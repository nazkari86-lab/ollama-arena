# Changelog

## 2.3.0

- `benchmark MODEL[,MODEL2]` — standardized 30-task Score (0–100) across 5 categories.
  `--compare` shows side-by-side; `--fail-below SCORE` exits 1 for CI quality gates.
- `match --share` — prints a copyable markdown results table at the end of a match.
- GitHub Actions template in `examples/github_actions/llm-benchmark.yml`.
- Web API: `/api/version`, `/api/task/{id}`, `/api/report/{model}` endpoints.
- Web: job log now includes truncated prompt and responses for live match view.
- Fix: `code_013` no longer hits `httpbin.org` — replaced with unittest.mock patch.
- Fix: web job_id collision resolved by appending timestamp.
- Fix: dead code `evaluate_answer()` removed from `reasoning.py`.
- README rewritten with `benchmark` as the headline command.

## 2.2.0

- Full response storage: every task now saves the prompt, both model
  responses, the expected answer, score, TPS, and latency to `arena.db`.
- `results` command — list recent matches; drill into any match with
  `--match <ID>` to see every prompt and response; `--full` for untruncated.
- `inspect <TASK_ID>` — see every time a specific task was run, across all
  models, with full A/B responses.
- `report` — per-model breakdown by category showing win rate, task count,
  and a strength/weakness verdict for each category.
- `match --verbose` (`-v`) — print prompt and both responses live during a run.
- Live match output now shows task instruction snippet alongside the score.

## 2.1.2

- Trim `pyproject.toml` keywords; mark as Beta.
- Drop the deprecated `OllamaClient` alias (use `OllamaBackend` or
  `Arena(backend=...)` directly).
- Rewrite examples in a terser style.
- Add `Makefile` and `.editorconfig`.

## 2.1.1

Docs and style pass. Behaviour unchanged.

- README rewritten to match the format conventional in this space
  (inspect_ai, simple-evals, lm-evaluation-harness): one-paragraph
  intro, install, quick start, scoring, limitations.
- Citations added for the built-in dataset loaders.
- Module docstrings shortened; decorative emoji and ASCII box dividers
  removed from source.
- Logo moved into a `<details>` block at the end of the README.

## 2.1.0

- `TransformersBackend` — in-process generation via PyTorch (lazy import,
  needs the `[hf]` extra).
- `LLMJudge` for open-ended responses. Pairs are graded in both
  orderings to suppress position bias.
- `Arena(judge_model=...)` switches tasks tagged `use_judge=True` to the
  judge path.
- CLI banner on bare invocation.

## 2.0.0

- Multi-backend support: Ollama plus OpenAI-compatible (vLLM,
  LM Studio, llama.cpp, OpenAI, Groq, Together, OpenRouter, ...).
- HuggingFace dataset loaders: HumanEval, MBPP, MBPP+, GSM8K, MMLU, BBH,
  MultiPL-E, HellaSwag, TruthfulQA, ARC.
- Sandboxed code execution for Python, JS, TS, Rust, Go, C++, Bash;
  optional Docker isolation.
- Plotly chart generators and a self-contained dashboard export.
- Per-generation performance log (tps, latency, ttft).
- Unsloth-based fine-tuning pipeline ending in an Ollama Modelfile.
- CI on Ubuntu and macOS, Python 3.10–3.12.

## 1.0.0

Initial release. Ollama-only ELO arena with hand-written tasks and a
basic Rich CLI.
