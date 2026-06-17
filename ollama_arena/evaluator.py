"""Per-task scorers and a router from task id/category to the right one."""
from __future__ import annotations
import logging, re, os
from typing import Any
from .utils import extract_code

log = logging.getLogger("arena.eval")


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

    # STRICT DOCKER ENFORCEMENT for safety
    result = run_in_language(full, language=language, timeout=task.get("timeout", 15), use_docker=True)
    
    if result.blocked:
        log.warning(f"[eval_coding] Blocked pattern detected: {result.error}")
        return 0.0
    if result.timed_out:
        log.warning(f"[eval_coding] Execution timed out ({task.get('id', 'unknown')})")
        return 0.0
    if not result.accepted:
        log.info(f"[eval_coding] Execution failed ({task.get('id', 'unknown')}) with exit code {result.exit_code}: {result.error}")
        
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

    if check == "contains_all":
        items = [str(i).strip().lower() for i in task.get("check_items", [expected])]
        return 1.0 if all(i in resp for i in items) else 0.0

    if check == "contains_any":
        items = [str(i).strip().lower() for i in task.get("check_items", [expected])]
        return 1.0 if any(i in resp for i in items) else 0.0

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


_CLEAN_PHRASES = (
    "clean", "no issue", "no bug", "no vulnerabilit", "no problem",
    "no flaw", "no error", "looks good", "looks safe", "looks correct",
    "looks fine", "appears clean", "appears safe", "no security",
    "nothing wrong", "nothing suspicious", "all good", "seems fine",
    "seems safe", "seems correct", "well written", "well-written",
    "no concern", "no weakness", "passes inspection",
)
_BUG_WORDS = ("vulnerabilit", "bug", "issue", "flaw", "error", "problem",
               "insecure", "unsafe", "wrong", "incorrect", "exploit")


def eval_inspection(task: dict, response: str) -> float:
    resp = response.lower()
    has_bug = task.get("has_bug", False)
    expected = [i.lower() for i in task.get("expected_issues", [])]
    if not has_bug:
        has_clean_phrase = any(p in resp for p in _CLEAN_PHRASES)
        has_bug_word = any(w in resp for w in _BUG_WORDS)
        if has_clean_phrase and not has_bug_word:
            return 1.0
        if has_clean_phrase:
            return 0.6
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


# JSON Evaluation
def eval_json(task: dict, response: str) -> float:
    """Evaluate JSON format conformance against expected_schema."""
    import json
    text = response.strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if m:
        text = m.group(1).strip()
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start:end+1]
            
    try:
        data = json.loads(text)
    except Exception:
        return 0.0

    schema = task.get("expected_schema")
    if not schema:
        return 1.0

    if not isinstance(data, dict):
        return 0.0

    correct_keys = 0
    for key, expected_type in schema.items():
        if key not in data:
            continue
        val = data[key]
        if expected_type == "string" and isinstance(val, str):
            correct_keys += 1
        elif expected_type == "integer" and isinstance(val, int) and not isinstance(val, bool):
            correct_keys += 1
        elif expected_type == "number" and isinstance(val, (int, float)) and not isinstance(val, bool):
            correct_keys += 1
        elif expected_type == "boolean" and isinstance(val, bool):
            correct_keys += 1
        elif expected_type == "list" and isinstance(val, list):
            correct_keys += 1
        elif expected_type == "dict" and isinstance(val, dict):
            correct_keys += 1

    total_keys = len(schema)
    if total_keys == 0:
        return 1.0
    return round(correct_keys / total_keys, 3)


# Router
def evaluate(task: dict, response: str) -> float:
    tid = task.get("id", "")
    cat = task.get("category", "")

    if cat == "json_format" or tid.startswith("json_"):
        return eval_json(task, response)
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

    if cat == "creative" or tid.startswith("crea_"):
        # Judge-scored tasks fall back to 0.5 when no judge is available.
        return 0.5

    log.warning(f"[eval] unknown task type: {tid} / cat={cat}")
    return 0.0


# Back-compat aliases
eval_reasoning = eval_text_answer
