"""
Universal dataset loader — pulls from HuggingFace Hub, caches locally,
normalizes into ollama-arena's task schema.
"""
from __future__ import annotations
import hashlib, json, logging, os, time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger("arena.datasets")

CACHE_DIR = Path(os.environ.get(
    "OLLAMA_ARENA_CACHE",
    str(Path.home() / ".cache" / "ollama_arena" / "datasets"),
))
CACHE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class DatasetInfo:
    name:        str
    hf_id:       str
    split:       str    = "test"
    config:      str    = ""
    category:    str    = "coding"
    description: str    = ""
    fetcher:     Optional[Callable] = None       # normalize one HF row → task dict
    license:     str    = ""
    url:         str    = ""
    n_tasks:     int    = 0


# ── HF row → task normalizers ────────────────────────────────────────────────
def _humaneval(row: dict, idx: int) -> dict:
    """OpenAI HumanEval: {task_id, prompt, canonical_solution, test, entry_point}."""
    prompt = row["prompt"].strip()
    test   = row["test"]
    entry  = row["entry_point"]
    # Build test wrapper that asserts via the HumanEval `check(candidate)` pattern
    test_code = (
        f"\n# tests\n{test}\n"
        f"check({entry})\n"
    )
    return {
        "id":          f"humaneval_{row['task_id'].split('/')[-1]}",
        "category":    "coding",
        "language":    "python",
        "difficulty":  "medium",
        "instruction": (
            f"Complete the following Python function. Only output the code, "
            f"no explanations:\n\n```python\n{prompt}\n```"
        ),
        "test_code":   test_code,
        "source":      "openai_humaneval",
    }


def _mbpp(row: dict, idx: int) -> dict:
    """Google MBPP: {task_id, text, code, test_list, ...}."""
    tests = "\n".join(row.get("test_list", []))
    return {
        "id":          f"mbpp_{row.get('task_id', idx)}",
        "category":    "coding",
        "language":    "python",
        "difficulty":  "easy",
        "instruction": f"{row['text']}\n\nWrite Python code only.",
        "test_code":   tests,
        "source":      "mbpp",
    }


def _gsm8k(row: dict, idx: int) -> dict:
    """GSM8K: {question, answer}.  Answer is e.g. '... #### 18'."""
    ans = row["answer"].strip()
    # Final answer after "####"
    final = ans.split("####")[-1].strip() if "####" in ans else ans
    return {
        "id":              f"gsm8k_{idx}",
        "category":        "math",
        "language":        "natural",
        "difficulty":      "medium",
        "instruction":     row["question"] + "\nAnswer with the final numeric answer only.",
        "expected_answer": final,
        "check":           "numeric_approx",
        "tolerance":       0,
        "source":          "gsm8k",
    }


def _mmlu(row: dict, idx: int) -> dict:
    """MMLU: {question, choices, answer (int 0-3)}."""
    choices = row["choices"]
    answer_idx = int(row["answer"])
    answer_letter = ["A", "B", "C", "D"][answer_idx]
    options = "\n".join(f"{l}. {c}" for l, c in zip(["A","B","C","D"], choices))
    return {
        "id":              f"mmlu_{row.get('subject','x')}_{idx}",
        "category":        "knowledge",
        "language":        "natural",
        "difficulty":      "medium",
        "instruction": (
            f"Question: {row['question']}\n{options}\n\n"
            f"Answer with only the letter (A, B, C, or D)."
        ),
        "expected_answer": answer_letter,
        "check":           "exact_prefix",
        "source":          "mmlu",
        "subject":         row.get("subject", ""),
    }


def _bbh(row: dict, idx: int) -> dict:
    """BBH: {input, target}."""
    return {
        "id":              f"bbh_{idx}",
        "category":        "reasoning",
        "language":        "natural",
        "difficulty":      "hard",
        "instruction":     row["input"],
        "expected_answer": str(row["target"]).strip(),
        "check":           "contains",
        "source":          "bbh",
    }


def _multipl_e(row: dict, idx: int) -> dict:
    """MultiPL-E: HumanEval translated to 22 languages.
    Fields: name, language, prompt, tests, stop_tokens."""
    lang = row.get("language", "py").lower()
    lang_map = {"py":"python","js":"javascript","ts":"typescript",
                "rs":"rust","go":"go","cpp":"cpp","sh":"bash"}
    out_lang = lang_map.get(lang, lang)
    return {
        "id":          f"multipl_{lang}_{idx}",
        "category":    "coding",
        "language":    out_lang,
        "difficulty":  "medium",
        "instruction": (
            f"Complete this {out_lang} function. Only code, no explanation:\n\n"
            f"{row['prompt']}"
        ),
        "test_code":   row.get("tests", ""),
        "source":      f"multipl_e_{lang}",
    }


def _hellaswag(row: dict, idx: int) -> dict:
    label = int(row.get("label", 0))
    endings = row.get("endings", [])
    answer = chr(ord("A") + label)
    options = "\n".join(f"{chr(65+i)}. {e}" for i, e in enumerate(endings))
    return {
        "id":              f"hellaswag_{idx}",
        "category":        "reasoning",
        "language":        "natural",
        "difficulty":      "medium",
        "instruction": (
            f"{row.get('ctx','')}\n{options}\n\n"
            f"Answer with only the letter (A–D)."
        ),
        "expected_answer": answer,
        "check":           "exact_prefix",
        "source":          "hellaswag",
    }


def _truthfulqa(row: dict, idx: int) -> dict:
    return {
        "id":              f"truthful_{idx}",
        "category":        "knowledge",
        "language":        "natural",
        "difficulty":      "hard",
        "instruction":     row["question"],
        "expected_answer": row.get("best_answer", "").strip(),
        "check":           "contains",
        "source":          "truthfulqa",
    }


def _arc(row: dict, idx: int) -> dict:
    choices = row["choices"]["text"]
    labels  = row["choices"]["label"]
    answer_label = row["answerKey"]
    options = "\n".join(f"{l}. {c}" for l, c in zip(labels, choices))
    return {
        "id":              f"arc_{row.get('id', idx)}",
        "category":        "knowledge",
        "language":        "natural",
        "difficulty":      "medium",
        "instruction": (
            f"Question: {row['question']}\n{options}\n\n"
            f"Answer with only the letter."
        ),
        "expected_answer": answer_label,
        "check":           "exact_prefix",
        "source":          "arc",
    }


# ── Registry ────────────────────────────────────────────────────────────────
REGISTRY: dict[str, DatasetInfo] = {
    "humaneval": DatasetInfo(
        name="humaneval", hf_id="openai_humaneval", split="test",
        category="coding", description="164 Python code-gen tasks",
        fetcher=_humaneval, license="MIT",
        url="https://huggingface.co/datasets/openai_humaneval",
    ),
    "mbpp": DatasetInfo(
        name="mbpp", hf_id="mbpp", split="test",
        category="coding", description="Mostly Basic Python Problems",
        fetcher=_mbpp, license="cc-by-4.0",
        url="https://huggingface.co/datasets/mbpp",
    ),
    "mbpp_plus": DatasetInfo(
        name="mbpp_plus", hf_id="evalplus/mbppplus", split="test",
        category="coding", description="MBPP+ extended test cases",
        fetcher=_mbpp, license="MIT",
        url="https://huggingface.co/datasets/evalplus/mbppplus",
    ),
    "gsm8k": DatasetInfo(
        name="gsm8k", hf_id="gsm8k", split="test", config="main",
        category="math", description="8.5K grade-school math word problems",
        fetcher=_gsm8k, license="MIT",
        url="https://huggingface.co/datasets/gsm8k",
    ),
    "mmlu": DatasetInfo(
        name="mmlu", hf_id="cais/mmlu", split="test", config="all",
        category="knowledge", description="57 subjects, 14K multiple choice",
        fetcher=_mmlu, license="MIT",
        url="https://huggingface.co/datasets/cais/mmlu",
    ),
    "bbh": DatasetInfo(
        name="bbh", hf_id="lukaemon/bbh", split="test", config="boolean_expressions",
        category="reasoning", description="Big-Bench Hard reasoning tasks",
        fetcher=_bbh, license="MIT",
        url="https://huggingface.co/datasets/lukaemon/bbh",
    ),
    "multipl_e": DatasetInfo(
        name="multipl_e", hf_id="nuprl/MultiPL-E", split="test",
        config="humaneval-py",
        category="coding", description="HumanEval in 22 programming languages",
        fetcher=_multipl_e, license="BSD-3",
        url="https://huggingface.co/datasets/nuprl/MultiPL-E",
    ),
    "hellaswag": DatasetInfo(
        name="hellaswag", hf_id="hellaswag", split="validation",
        category="reasoning", description="Common-sense reasoning",
        fetcher=_hellaswag, license="MIT",
        url="https://huggingface.co/datasets/hellaswag",
    ),
    "truthfulqa": DatasetInfo(
        name="truthfulqa", hf_id="truthful_qa", split="validation",
        config="generation",
        category="knowledge", description="Honesty / factual accuracy",
        fetcher=_truthfulqa, license="Apache-2.0",
        url="https://huggingface.co/datasets/truthful_qa",
    ),
    "arc": DatasetInfo(
        name="arc", hf_id="ai2_arc", split="test", config="ARC-Challenge",
        category="knowledge", description="AI2 Science questions",
        fetcher=_arc, license="cc-by-sa-4.0",
        url="https://huggingface.co/datasets/ai2_arc",
    ),
}


# ── Public API ───────────────────────────────────────────────────────────────
def available_datasets() -> list[dict]:
    return [
        {"name": d.name, "hf_id": d.hf_id, "category": d.category,
         "description": d.description, "license": d.license, "url": d.url,
         "cached": _cache_path(d).exists()}
        for d in REGISTRY.values()
    ]


def cached_datasets() -> list[str]:
    if not CACHE_DIR.exists():
        return []
    return [p.stem for p in CACHE_DIR.glob("*.json")]


def _cache_path(info: DatasetInfo) -> Path:
    h = hashlib.md5(
        f"{info.hf_id}::{info.config}::{info.split}".encode()
    ).hexdigest()[:8]
    return CACHE_DIR / f"{info.name}_{h}.json"


def refresh_dataset(name: str, limit: int | None = None) -> int:
    """Force re-download from HuggingFace and overwrite cache."""
    info = REGISTRY.get(name)
    if not info:
        raise ValueError(f"Unknown dataset: {name}")
    tasks = _download(info, limit=limit)
    path = _cache_path(info)
    path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2))
    log.info(f"[datasets] refreshed {name}: {len(tasks)} tasks → {path}")
    return len(tasks)


def load_dataset(name: str, limit: int | None = None,
                 refresh: bool = False) -> list[dict]:
    """
    Load a benchmark dataset, normalized to ollama-arena task schema.

    First call downloads from HF (requires `pip install datasets`); subsequent
    calls read from local cache. Pass refresh=True to force re-download.
    """
    info = REGISTRY.get(name)
    if not info:
        raise ValueError(f"Unknown dataset '{name}'. "
                         f"Available: {list(REGISTRY.keys())}")
    path = _cache_path(info)
    if path.exists() and not refresh:
        tasks = json.loads(path.read_text())
    else:
        tasks = _download(info, limit=limit)
        path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2))
        log.info(f"[datasets] cached {name}: {len(tasks)} tasks → {path}")
    if limit:
        tasks = tasks[:limit]
    return tasks


def _download(info: DatasetInfo, limit: int | None = None) -> list[dict]:
    """Download from HuggingFace and normalize."""
    try:
        from datasets import load_dataset as hf_load
    except ImportError:
        raise RuntimeError(
            "Install HuggingFace datasets to download benchmarks:\n"
            "    pip install 'ollama-arena[datasets]'"
        )
    kwargs = {}
    if info.config:
        kwargs["name"] = info.config
    log.info(f"[datasets] downloading {info.hf_id} ({info.config or 'default'}) [{info.split}]")
    ds = hf_load(info.hf_id, split=info.split, **kwargs)
    n = limit or len(ds)
    tasks = []
    for i, row in enumerate(ds):
        if i >= n:
            break
        try:
            tasks.append(info.fetcher(dict(row), i))
        except Exception as e:
            log.debug(f"[datasets] skip row {i} of {info.name}: {e}")
    return tasks
