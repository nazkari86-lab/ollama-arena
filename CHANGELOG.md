# Changelog

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
