"""Task evaluators for each benchmark category."""
from __future__ import annotations
import re
import logging

log = logging.getLogger("arena.eval")


def extract_code(text: str) -> str:
    """Extract code block from LLM response."""
    m = re.search(r"```(?:python|py|bash|sh)?\s*(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    stripped = text.strip()
    # Looks like raw code
    if any(stripped.startswith(p) for p in ("import ", "from ", "def ", "class ", "#!", "async ")):
        return stripped
    return stripped


def eval_coding(task: dict, response: str) -> float:
    """Execute generated code + assert tests. Returns 0.0 or 1.0."""
    from .sandbox import run_with_tests
    code = extract_code(response)
    if not code:
        return 0.0
    test_code = task.get("test_code", "")
    if not test_code:
        return 0.5  # no tests — partial credit
    result = run_with_tests(code, test_code, timeout_sec=10)
    if result.timed_out:
        log.debug(f"[eval] {task['id']}: timeout")
    elif result.error:
        log.debug(f"[eval] {task['id']}: {result.error[:80]}")
    return 1.0 if result.accepted else 0.0


def eval_reasoning(task: dict, response: str) -> float:
    """Exact/contains/numeric match for reasoning tasks."""
    resp = response.strip().lower()
    expected = str(task.get("expected_answer", "")).lower()
    check = task.get("check", "contains")

    if check == "exact":
        # Allow answer anywhere in first 50 chars
        return 1.0 if expected in resp[:80] else 0.0

    if check == "exact_prefix":
        return 1.0 if resp.startswith(expected) else 0.0

    if check == "contains":
        return 1.0 if expected in resp else 0.0

    if check == "numeric_approx":
        tolerance = task.get("tolerance", 2)
        try:
            nums = [float(n) for n in re.findall(r"-?\d+\.?\d*", resp)]
            target = float(expected)
            return 1.0 if any(abs(n - target) <= tolerance for n in nums) else 0.0
        except Exception:
            return 0.0

    return 0.0


def eval_security(task: dict, response: str) -> float:
    """Score CVE/vulnerability detection by keyword matching."""
    resp = response.lower()
    expected_vulns = [v.lower() for v in task.get("expected_vulns", [])]
    expected_sev = task.get("expected_severity", "").lower()

    if not expected_vulns:
        return 0.5

    detected = sum(1 for v in expected_vulns if any(word in resp for word in v.split("_")))
    vuln_score = detected / len(expected_vulns)
    sev_score = 1.0 if expected_sev and expected_sev in resp else 0.5
    return round(vuln_score * 0.7 + sev_score * 0.3, 3)


def eval_inspection(task: dict, response: str) -> float:
    """Precision/recall for code inspection tasks."""
    resp = response.lower()
    has_bug = task.get("has_bug", False)
    expected_issues = [i.lower() for i in task.get("expected_issues", [])]

    if not has_bug:
        if any(w in resp for w in ("clean", "no issue", "no vulnerabilit", "no bug", "looks good")):
            return 1.0
        return 0.3  # false positive penalty

    if not expected_issues:
        return 0.5
    detected = sum(1 for issue in expected_issues
                   if any(word in resp for word in issue.split()))
    return round(detected / len(expected_issues), 3)


def eval_planning(task: dict, response: str) -> float:
    """Keyword coverage + length heuristic for planning tasks."""
    resp = response.lower()
    key_components = [c.lower() for c in task.get("key_components", [])]

    if not key_components:
        return 0.5

    found = sum(1 for c in key_components if c in resp)
    component_score = found / len(key_components)

    words = len(response.split())
    length_score = min(1.0, words / 150) if words < 150 else (1.0 if words <= 800 else 0.9)

    return round(component_score * 0.7 + length_score * 0.3, 3)


# ── Router ──────────────────────────────────────────────────────────────────

def evaluate(task: dict, response: str) -> float:
    """Route task to correct evaluator. Returns score 0.0–1.0."""
    tid = task.get("id", "")
    cat = task.get("category", "")

    if tid.startswith("code_") or cat == "coding":
        return eval_coding(task, response)
    if tid.startswith("reas_") or cat == "reasoning":
        return eval_reasoning(task, response)
    if tid.startswith("sec_") or cat == "security":
        return eval_security(task, response)
    if tid.startswith("insp_") or cat == "inspection":
        return eval_inspection(task, response)
    if tid.startswith("plan_") or cat == "planning":
        return eval_planning(task, response)

    log.warning(f"[eval] unknown task type: {tid}")
    return 0.0
