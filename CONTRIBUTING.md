# Contributing

Contributions are welcome. The areas most useful to outside contributors:

1. **Benchmark tasks** — new domain-specific tasks for each category
2. **HuggingFace dataset loaders** — register a normalizer in
   `ollama_arena/datasets/loader.py`
3. **Language sandboxes** — add a runner in `ollama_arena/sandboxes/runner.py`
4. **Backends** — implement the `Backend` protocol from
   `ollama_arena/backends/base.py`

## Development setup

```bash
git clone https://github.com/nazkari86-lab/ollama-arena
cd ollama-arena
pip install -e ".[dev,all]"
pytest -q
ruff check ollama_arena
```

## Adding a HuggingFace dataset

```python
# ollama_arena/datasets/loader.py
def _my_dataset(row: dict, idx: int) -> dict:
    return {
        "id":              f"mybench_{idx}",
        "category":        "reasoning",
        "language":        "natural",
        "difficulty":      "medium",
        "instruction":     row["question"],
        "expected_answer": row["answer"],
        "check":           "contains",
        "source":          "my-dataset",
    }

REGISTRY["mybench"] = DatasetInfo(
    name="mybench", hf_id="my-org/my-dataset", split="test",
    category="reasoning", description="...", fetcher=_my_dataset,
    license="MIT", url="https://huggingface.co/datasets/my-org/my-dataset",
)
```

## Adding a language sandbox

```python
# ollama_arena/sandboxes/runner.py
def _run_zig(code: str, timeout: int, tmp: Path) -> RunResult:
    src = tmp / "main.zig"
    src.write_text(code)
    return _exec(["zig", "run", str(src)], timeout, Language.ZIG)

_RUNNERS[Language.ZIG] = _run_zig
```

Add the language to the `Language` enum and `_RUNTIME_CHECKS`.

## Adding a backend

```python
# ollama_arena/backends/my_backend.py
class MyBackend:
    name = "my-backend"

    def generate(self, model: str, prompt: str, **opts) -> GenResult: ...
    def list_models(self) -> list[str]: ...
    def is_alive(self) -> bool: ...
```

Re-export from `backends/__init__.py`.

## Style

- Line length 100
- Type hints required on public functions
- Run `ruff check ollama_arena` before submitting
- New features should add at least one test in `tests/`

## Submitting changes

1. Fork → branch → commit
2. Make sure `pytest` passes
3. Open a PR describing the change and motivation

For larger changes please open an issue first to discuss the design.
