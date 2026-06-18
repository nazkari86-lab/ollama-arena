# Contributing

Useful contributions in rough order of impact: new HuggingFace dataset
loaders, new language sandboxes, new backends, additional built-in tasks.

## Development

```
git clone https://github.com/nazkari86-lab/ollama-arena
cd ollama-arena
pip install -e ".[dev,all]"
pytest -q
ruff check ollama_arena tests
```

## Adding a HuggingFace dataset

Add a row normalizer and a `DatasetInfo` entry in
`ollama_arena/datasets/loader.py`:

```python
def _my_dataset(row, idx):
    return {
        "id": f"mybench_{idx}",
        "category": "reasoning",
        "language": "natural",
        "difficulty": "medium",
        "instruction": row["question"],
        "expected_answer": row["answer"],
        "check": "contains",
        "source": "my-dataset",
    }

REGISTRY["mybench"] = DatasetInfo(
    name="mybench", hf_id="my-org/my-dataset", split="test",
    category="reasoning", fetcher=_my_dataset,
)
```

The arena calls the fetcher once per row when downloading. Output must
follow the task schema documented in `loader.py`.

## Adding a language sandbox

Register a runner in `ollama_arena/sandboxes/runner.py`:

```python
def _run_zig(code, timeout, tmp):
    src = tmp / "main.zig"
    src.write_text(code)
    return _exec(["zig", "run", str(src)], timeout, Language.ZIG)

_RUNNERS[Language.ZIG] = _run_zig
```

Add the language to the `Language` enum (`sandboxes/base.py`) and to
`_RUNTIME_CHECKS` so it gets picked up by `available_languages()`.

If you want Docker isolation, register an image in `_DOCKER_IMAGES`.

## Adding a backend

Implement `Backend` from `ollama_arena/backends/base.py` and re-export
from `backends/__init__.py`:

```python
class MyBackend:
    name = "my-backend"

    def generate(self, model, prompt, **opts): ...
    def list_models(self): ...
    def is_alive(self): ...
```

The Arena calls `generate()` twice per task (once per model in the
pair). It must return a `GenResult`.

## Style

100-column lines, type hints on public functions, `ruff check` clean.
Tests are pytest functions in `tests/`; the smoke suite must pass
without any backend running.

## Architecture decisions

For significant design changes (new storage backend, MCP registry refactor,
security policy changes), add a short ADR under `docs/adr/` or note the
decision in the PR description before merging.

## PRs

For larger changes please open an issue first to discuss the design.
