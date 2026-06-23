"""Per-task scorers and a router from task id/category to the right one."""
from __future__ import annotations
import logging
import re
import os
from typing import Any
from .utils import extract_code

log = logging.getLogger("arena.eval")

# Cascade evaluator (OpenCompass-inspired): try the cheap rule-based check
# first and only escalate to the LLM judge when it can't confirm a confident
# pass. Opt-in and default OFF so existing judge-call behavior (and its
# cost/latency profile) is unchanged unless explicitly enabled.
_CASCADE_EVAL_ENABLED = os.getenv("ARENA_CASCADE_EVAL", "0") == "1"


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
def eval_text_answer(task: dict, response: str, judge: Any | None = None) -> float:
    """Evaluates knowledge and reasoning tasks.
    Supports 'exact', 'contains', 'contains_all', and 'semantic' (via judge).
    """
    resp = response.strip().lower()
    expected = str(task.get("expected_answer", "")).strip().lower()
    check = task.get("check", "contains")
    tid = task.get("id", "unknown")

    if not expected:
        return 0.5

    wants_judge = bool((check == "semantic" or task.get("use_judge")) and judge)

    # Cascade (opt-in via ARENA_CASCADE_EVAL=1): when a real rule-based
    # check is configured (not an explicit "semantic" request), try it
    # first. A confident pass skips the judge call entirely -- only
    # ambiguous (non-matching) cases escalate.
    if wants_judge and _CASCADE_EVAL_ENABLED and check != "semantic":
        cheap_score = _rule_based_text_score(resp, expected, check, task)
        if cheap_score >= 1.0:
            return cheap_score

    # Semantic check (judge) — unchanged default path.
    if wants_judge:
        try:
            return judge.evaluate_single(task["instruction"], response, reference=expected)
        except Exception as e:
            log.warning(f"[eval] semantic check failed for {tid}: {e}")

    return _rule_based_text_score(resp, expected, check, task)


def _rule_based_text_score(resp: str, expected: str, check: str, task: dict) -> float:
    """Pure string-matching scorer, no judge involved. `resp`/`expected`
    are already lower-cased/stripped by the caller."""
    if check == "exact":
        return 1.0 if expected == resp else 0.0

    if check == "exact_prefix":
        cleaned = re.sub(r"^[^a-zA-Z0-9]+", "", resp)
        return 1.0 if cleaned.startswith(expected) else 0.0

    if check == "contains":
        # Reliability fix: avoid false positives like "not paris" or "paris or lyon"
        # Use word boundaries to avoid partial matches
        pattern = rf"\b{re.escape(expected)}\b"
        matches = list(re.finditer(pattern, resp))

        if not matches:
            return 0.0

        # Check for simple negative context: "not [expected]", "instead of [expected]"
        negatives = ["not ", "instead of ", "rather than ", "never ", "doesn't ", "don't "]
        for match in matches:
            start = max(0, match.start() - 20)
            context = resp[start:match.start()]
            if not any(neg in context for neg in negatives):
                return 1.0 # Found at least one positive mention

        return 0.0

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


def _tools_from_trace(trace: list | None) -> list[dict]:
    """Extracted tool info (name, arguments) from agent_trace steps."""
    if not trace:
        return []
    tools: list[dict] = []
    for step in trace:
        if not isinstance(step, dict):
            continue
        # We prefer tool_results if available because it has parsed arguments
        results = step.get("tool_results")
        if results:
            for r in results:
                tools.append({"name": r.get("name"), "arguments": r.get("arguments")})
        else:
            # Fallback to tool_calls from assistant message
            for call in step.get("tool_calls") or []:
                if not isinstance(call, dict):
                    continue
                fn = call.get("function") or {}
                name = fn.get("name") if isinstance(fn, dict) else None
                import json
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                except Exception:
                    args = {}
                if name:
                    tools.append({"name": name, "arguments": args})
    return tools


def _validate_args(actual: dict, expected: dict) -> bool:
    """Check if actual arguments match expected patterns (regex)."""
    if not expected:
        return True
    if not actual:
        return False
    for key, pattern in expected.items():
        val = str(actual.get(key, ""))
        if not re.search(str(pattern), val, re.IGNORECASE):
            return False
    return True


def _subsequence_score(actual_tools: list[dict], expected: list[str], expected_args: dict | None = None) -> float:
    """1.0 if expected tool names appear in order within actual. Partial if args match."""
    if not expected:
        return 0.5
    if not actual_tools:
        return 0.0
    
    ei = 0
    correct_with_args = 0
    
    for tool in actual_tools:
        name = tool.get("name")
        args = tool.get("arguments") or {}
        
        if ei < len(expected) and name == expected[ei]:
            # Found the expected tool in order
            arg_match = True
            if expected_args and expected[ei] in expected_args:
                arg_match = _validate_args(args, expected_args[expected[ei]])
            
            if arg_match:
                correct_with_args += 1
            ei += 1
            
    # Base score for sequence + bonus for correct args
    seq_score = ei / len(expected)
    arg_bonus = correct_with_args / len(expected)
    
    # We want 1.0 only if both sequence and args are perfect
    return round(seq_score * 0.5 + arg_bonus * 0.5, 3)


def eval_agent_trajectory(task: dict, trace: list | None) -> float:
    """Score multi-step MCP trajectories via expected_tools or expected_tool."""
    expected_tools = task.get("expected_tools")
    expected_args = task.get("expected_args")  # Can be dict: {tool_name: {arg: pattern}}
    
    actual_tools = _tools_from_trace(trace)
    
    if expected_tools:
        return _subsequence_score(actual_tools, list(expected_tools), expected_args)
    
    expected_tool = task.get("expected_tool")
    if expected_tool:
        # Wrap single tool as a list for _subsequence_score
        # expected_args might be just {arg: pattern} if single tool
        e_args = {expected_tool: expected_args} if expected_args and expected_tool not in expected_args else expected_args
        return _subsequence_score(actual_tools, [expected_tool], e_args)
    
    return 0.5


def eval_vision(task: dict, response: str) -> float:
    """Score vision tasks by keyword overlap in the model response."""
    keywords = task.get("expected_keywords") or []
    if not keywords:
        return 0.5 if response.strip() else 0.0
    text = response.lower()
    hits = sum(1 for kw in keywords if kw.lower() in text)
    return round(hits / len(keywords), 3)


def eval_tool_use(task: dict, response: str, trace: list | None = None) -> float:
    """Evaluates MCP tool invocation from agent trace and/or response JSON."""
    import json

    traj = eval_agent_trajectory(task, trace)
    if task.get("expected_tools") or task.get("expected_tool"):
        if traj >= 1.0:
            return 1.0
        if trace and traj > 0:
            return traj

    expected_tool = task.get("expected_tool")
    expected_args = task.get("expected_args")
    if not expected_tool:
        return traj if trace else 0.5

    try:
        data = json.loads(response)
        if isinstance(data, list):
            for call in data:
                func = call.get("function", {})
                name = func.get("name")
                if name == expected_tool:
                    args = func.get("arguments")
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {}
                    if _validate_args(args, expected_args or {}):
                        return 1.0
                    return 0.8 # Correct tool, wrong args
    except (json.JSONDecodeError, TypeError):
        pass

    if expected_tool.lower() in response.lower():
        return 0.4 # Just mentioned it

    return 0.0


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
def evaluate(task: dict, response: str, trace: list | None = None, judge: Any | None = None) -> float | None:
    tid = task.get("id", "")
    cat = task.get("category", "")

    if cat == "json_format" or tid.startswith("json_"):
        return eval_json(task, response)
    if cat == "coding" or tid.startswith(("code_", "humaneval_", "mbpp_", "multipl_")):
        return eval_coding(task, response)
    if cat in ("math", "reasoning", "knowledge") or tid.startswith(
        ("reas_", "gsm8k_", "mmlu_", "bbh_", "hellaswag_", "truthful_", "arc_")
    ):
        return eval_text_answer(task, response, judge=judge)
    if cat == "security" or tid.startswith("sec_"):
        return eval_security(task, response)
    if cat == "inspection" or tid.startswith("insp_"):
        return eval_inspection(task, response)
    if cat == "planning" or tid.startswith("plan_"):
        return eval_planning(task, response)
    if cat == "tool_use" or tid.startswith("tool_"):
        return eval_tool_use(task, response, trace=trace)
    if cat == "vision" or tid.startswith("vis_"):
        return eval_vision(task, response)

    if cat == "creative" or tid.startswith("crea_"):
        # Returns None to indicate that a judge is required but not provided.
        if judge:
            try:
                return judge.evaluate_single(task["instruction"], response)
            except Exception as e:
                log.warning(f"[eval] creative judge eval failed: {e}")
        return None

    log.warning(f"[eval] unknown task type: {tid} / cat={cat}")
    return 0.0


# Back-compat aliases
eval_reasoning = eval_text_answer
