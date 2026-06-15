"""Per-task scorers and a router from task id/category to the right one."""
from __future__ import annotations
import logging, re
from typing import Any

log = logging.getLogger("arena.eval")


# Code-block extraction
_FENCED = re.compile(r"```(?:python|py|javascript|js|typescript|ts|rust|rs|go|cpp|c\+\+|bash|sh)?\s*(.*?)```",
                     re.DOTALL | re.IGNORECASE)


def extract_code(text: str, language: str = "python") -> str:
    """Pull the first fenced code block; fall back to raw text if it
    already looks like source in the requested language."""
    m = _FENCED.search(text)
    if m:
        return m.group(1).strip()
    stripped = text.strip()
    py_prefixes = ("import ", "from ", "def ", "class ", "async ", "#!", "if ", "@")
    js_prefixes = ("import ", "const ", "let ", "var ", "function ", "class ", "async ")
    rust_prefixes = ("use ", "fn ", "pub ", "struct ", "impl ", "mod ", "#[")
    go_prefixes = ("package ", "import ", "func ")
    cpp_prefixes = ("#include", "int ", "void ", "auto ", "class ", "namespace ", "using ")
    prefix_map = {
        "python": py_prefixes, "javascript": js_prefixes, "typescript": js_prefixes,
        "rust": rust_prefixes, "go": go_prefixes, "cpp": cpp_prefixes,
    }
    prefixes = prefix_map.get(language, py_prefixes)
    if any(stripped.startswith(p) for p in prefixes):
        return stripped
    return stripped


# Coding (executable)
def eval_coding(task: dict, response: str) -> float:
    """1.0 if generated code + test_code exit 0 inside the sandbox."""
    from .sandboxes import run_in_language
    language = task.get("language", "python")
    code = extract_code(response, language)
    if not code:
        return 0.0
    test = task.get("test_code", "")
    if not test:
        return 0.5
    full = code + "\n" + test
    result = run_in_language(full, language=language, timeout=task.get("timeout", 15))
    if result.blocked:
        return 0.0
    if result.timed_out:
        return 0.0
    return 1.0 if result.accepted else 0.0


# Reasoning / math / knowledge (string match)
def eval_text_answer(task: dict, response: str) -> float:
    resp = response.strip().lower()
    expected = str(task.get("expected_answer", "")).strip().lower()
    check = task.get("check", "contains")

    if not expected:
        return 0.5

    if check == "exact":
        return 1.0 if expected in resp[:120] else 0.0

    if check == "exact_prefix":
        cleaned = re.sub(r"^[^a-zA-Z0-9]+", "", resp)
        return 1.0 if cleaned.startswith(expected) else 0.0

    if check == "contains":
        return 1.0 if expected in resp else 0.0

    if check == "numeric_approx":
        tolerance = task.get("tolerance", 2)
        try:
            nums = [float(n.replace(",", "")) for n in re.findall(r"-?\d+\.?\d*", resp)]
            target = float(expected.replace(",", ""))
            return 1.0 if any(abs(n - target) <= tolerance for n in nums) else 0.0
        except Exception:
            return 0.0

    return 0.0


# Security & inspection (keyword presence)
def eval_security(task: dict, response: str) -> float:
    resp = response.lower()
    expected = [v.lower() for v in task.get("expected_vulns", [])]
    expected_sev = task.get("expected_severity", "").lower()
    if not expected:
        return 0.5
    detected = sum(1 for v in expected if any(w in resp for w in v.split("_")))
    vuln_score = detected / len(expected)
    sev_score = 1.0 if expected_sev and expected_sev in resp else 0.5
    return round(vuln_score * 0.7 + sev_score * 0.3, 3)


def eval_inspection(task: dict, response: str) -> float:
    resp = response.lower()
    has_bug = task.get("has_bug", False)
    expected = [i.lower() for i in task.get("expected_issues", [])]
    if not has_bug:
        if any(w in resp for w in ("clean", "no issue", "no vulnerabilit",
                                     "no bug", "looks good", "looks safe")):
            return 1.0
        return 0.3
    if not expected:
        return 0.5
    detected = sum(1 for issue in expected if any(w in resp for w in issue.split()))
    return round(detected / len(expected), 3)


def eval_planning(task: dict, response: str) -> float:
    resp = response.lower()
    keys = [c.lower() for c in task.get("key_components", [])]
    if not keys:
        return 0.5
    found = sum(1 for c in keys if c in resp)
    component_score = found / len(keys)
    words = len(response.split())
    length_score = min(1.0, words / 150) if words < 150 else (1.0 if words <= 800 else 0.9)
    return round(component_score * 0.7 + length_score * 0.3, 3)


# Router
def evaluate(task: dict, response: str) -> float:
    tid = task.get("id", "")
    cat = task.get("category", "")

    if cat == "coding" or tid.startswith(("code_", "humaneval_", "mbpp_", "multipl_")):
        return eval_coding(task, response)
    if cat in ("math", "reasoning", "knowledge") or tid.startswith(
        ("reas_", "gsm8k_", "mmlu_", "bbh_", "hellaswag_", "truthful_", "arc_")
    ):
        return eval_text_answer(task, response)
    if cat == "security" or tid.startswith("sec_"):
        return eval_security(task, response)
    if cat == "inspection" or tid.startswith("insp_"):
        return eval_inspection(task, response)
    if cat == "planning" or tid.startswith("plan_"):
        return eval_planning(task, response)

    log.warning(f"[eval] unknown task type: {tid} / cat={cat}")
    return 0.0


# Back-compat aliases
eval_reasoning = eval_text_answer
