# Changelog

## 2.1.0

### Added
- `TransformersBackend` for direct in-process inference via HuggingFace
  Transformers (no HTTP). Lazy-loaded; install with
  `pip install 'ollama-arena[hf]'`.
- `LLMJudge` / `JudgeResult` — pair-wise LLM-as-judge for open-ended tasks,
  with order-swap symmetrization to mitigate position bias.
- `Arena(judge_model=...)` enables judge scoring for tasks tagged
  `use_judge=True`.
- CLI banner shown when invoking `ollama-arena` without a subcommand and
  when starting the web dashboard.
- `CONTRIBUTING.md` and `CODE_OF_CONDUCT.md`.

### Changed
- Repository assets and CLI output cleaned of decorative emoji to match a
  more conventional library style.
- README rewritten as a reference document (architecture, scoring matrix,
  full CLI synopsis); marketing copy removed.

## 2.0.0

Multi-backend, HuggingFace dataset loaders, multi-language sandboxed code
execution, Plotly visualization, performance tracking, Unsloth fine-tuning
pipeline, CI for Ubuntu and macOS on Python 3.10–3.12. See git log
`60f2107..main` for the full diff.

## 1.0.0

Initial release. Ollama-only ELO arena with hand-written tasks, SQLite ELO
store, Rich CLI, and a basic FastAPI dashboard.
