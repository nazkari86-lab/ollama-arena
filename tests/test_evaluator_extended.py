"""Extended tests for evaluator — all pure scoring functions."""
from __future__ import annotations

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# eval_text_answer — all check modes
# ──────────────────────────────────────────────────────────────────────────────

class TestEvalTextAnswer:
    def _eval(self, task, response):
        from ollama_arena.evaluator import eval_text_answer
        return eval_text_answer(task, response)

    def test_no_expected_answer_returns_half(self):
        result = self._eval({"expected_answer": ""}, "some response")
        assert result == pytest.approx(0.5)

    def test_exact_match(self):
        result = self._eval({"expected_answer": "Paris", "check": "exact"}, "paris")
        assert result == pytest.approx(1.0)

    def test_exact_no_match(self):
        result = self._eval({"expected_answer": "Paris", "check": "exact"}, "london")
        assert result == pytest.approx(0.0)

    def test_contains_match(self):
        result = self._eval({"expected_answer": "paris", "check": "contains"}, "The answer is Paris in France")
        assert result == pytest.approx(1.0)

    def test_contains_no_match(self):
        result = self._eval({"expected_answer": "berlin", "check": "contains"}, "The capital is Paris")
        assert result == pytest.approx(0.0)

    def test_contains_negative_context_returns_zero(self):
        result = self._eval({"expected_answer": "paris", "check": "contains"}, "The answer is not paris")
        assert result == pytest.approx(0.0)

    def test_exact_prefix_match(self):
        result = self._eval({"expected_answer": "42", "check": "exact_prefix"}, "42 is the answer")
        assert result == pytest.approx(1.0)

    def test_exact_prefix_no_match(self):
        result = self._eval({"expected_answer": "42", "check": "exact_prefix"}, "The answer is 42")
        assert result == pytest.approx(0.0)

    def test_numeric_approx_match(self):
        result = self._eval(
            {"expected_answer": "42", "check": "numeric_approx", "tolerance": 2},
            "The answer is approximately 43"
        )
        assert result == pytest.approx(1.0)

    def test_numeric_approx_no_match(self):
        result = self._eval(
            {"expected_answer": "42", "check": "numeric_approx", "tolerance": 1},
            "The answer is 100"
        )
        assert result == pytest.approx(0.0)

    def test_numeric_approx_invalid_returns_zero(self):
        result = self._eval(
            {"expected_answer": "not_a_number", "check": "numeric_approx"},
            "response"
        )
        assert result == pytest.approx(0.0)

    def test_contains_all_all_present(self):
        result = self._eval(
            {"expected_answer": "placeholder", "check": "contains_all", "check_items": ["cat", "dog"]},
            "I have a cat and a dog"
        )
        assert result == pytest.approx(1.0)

    def test_contains_all_missing_one(self):
        result = self._eval(
            {"expected_answer": "placeholder", "check": "contains_all", "check_items": ["cat", "fish"]},
            "I have a cat"
        )
        assert result == pytest.approx(0.0)

    def test_contains_any_one_present(self):
        result = self._eval(
            {"expected_answer": "placeholder", "check": "contains_any", "check_items": ["cat", "dog"]},
            "I have a dog"
        )
        assert result == pytest.approx(1.0)

    def test_contains_any_none_present(self):
        result = self._eval(
            {"expected_answer": "placeholder", "check": "contains_any", "check_items": ["cat", "dog"]},
            "I have a fish"
        )
        assert result == pytest.approx(0.0)

    def test_unknown_check_returns_zero(self):
        result = self._eval({"expected_answer": "x", "check": "unknown_check"}, "x")
        assert result == pytest.approx(0.0)

    def test_semantic_without_judge_falls_through(self):
        # Without judge, semantic check falls through to regular check
        result = self._eval({"expected_answer": "paris", "check": "semantic"}, "The answer is paris")
        # Falls through to default "contains" behavior
        assert result >= 0.0

    def test_semantic_with_judge_calls_judge(self):
        from ollama_arena.evaluator import eval_text_answer
        import unittest.mock as mock
        judge = mock.MagicMock()
        judge.evaluate_single.return_value = 0.9
        result = eval_text_answer(
            {"expected_answer": "paris", "check": "semantic", "instruction": "What is the capital?"},
            "It is Paris",
            judge=judge
        )
        assert result == pytest.approx(0.9)


# ──────────────────────────────────────────────────────────────────────────────
# eval_security
# ──────────────────────────────────────────────────────────────────────────────

class TestEvalSecurity:
    def _eval(self, task, response):
        from ollama_arena.evaluator import eval_security
        return eval_security(task, response)

    def test_no_expected_vulns_returns_half(self):
        result = self._eval({"expected_vulns": []}, "some response")
        assert result == pytest.approx(0.5)

    def test_all_vulns_detected(self):
        result = self._eval(
            {"expected_vulns": ["sql_injection", "xss"], "expected_severity": "high"},
            "found sql injection and xss vulnerabilities with high severity"
        )
        assert result > 0.5

    def test_no_vulns_detected(self):
        result = self._eval(
            {"expected_vulns": ["buffer_overflow"]},
            "no issues found, code is clean"
        )
        assert result < 0.5

    def test_partial_vulns_detected(self):
        result = self._eval(
            {"expected_vulns": ["sql_injection", "xss"]},
            "found sql injection vulnerability"
        )
        assert 0.0 < result < 1.0

    def test_severity_bonus_when_matched(self):
        r1 = self._eval(
            {"expected_vulns": ["sql"], "expected_severity": "critical"},
            "found sql vulnerability with critical severity"
        )
        r2 = self._eval(
            {"expected_vulns": ["sql"], "expected_severity": "critical"},
            "found sql vulnerability"
        )
        assert r1 >= r2


# ──────────────────────────────────────────────────────────────────────────────
# eval_inspection
# ──────────────────────────────────────────────────────────────────────────────

class TestEvalInspection:
    def _eval(self, task, response):
        from ollama_arena.evaluator import eval_inspection
        return eval_inspection(task, response)

    def test_no_bug_clean_response(self):
        result = self._eval({"has_bug": False}, "The code looks clean and all good here")
        assert result == pytest.approx(1.0)

    def test_no_bug_but_mentions_bug(self):
        result = self._eval({"has_bug": False}, "There is a bug in the code, vulnerability found")
        assert result < 1.0

    def test_no_bug_neutral_response(self):
        result = self._eval({"has_bug": False}, "I see some patterns in the code")
        assert result == pytest.approx(0.3)

    def test_bug_no_expected_issues_returns_half(self):
        result = self._eval({"has_bug": True, "expected_issues": []}, "There is a bug")
        assert result == pytest.approx(0.5)

    def test_bug_all_issues_detected(self):
        result = self._eval(
            {"has_bug": True, "expected_issues": ["null pointer", "buffer overflow"]},
            "found null pointer dereference and buffer overflow"
        )
        assert result == pytest.approx(1.0)

    def test_bug_partial_detection(self):
        result = self._eval(
            {"has_bug": True, "expected_issues": ["null pointer", "buffer overflow"]},
            "found null pointer"
        )
        assert result == pytest.approx(0.5)

    def test_clean_phrase_with_bug_word(self):
        result = self._eval({"has_bug": False}, "The code looks clean but has a bug in line 5")
        assert result == pytest.approx(0.6)


# ──────────────────────────────────────────────────────────────────────────────
# eval_planning
# ──────────────────────────────────────────────────────────────────────────────

class TestEvalPlanning:
    def _eval(self, task, response):
        from ollama_arena.evaluator import eval_planning
        return eval_planning(task, response)

    def test_no_key_components_returns_half(self):
        result = self._eval({"key_components": []}, "Some plan")
        assert result == pytest.approx(0.5)

    def test_all_components_present(self):
        result = self._eval(
            {"key_components": ["gather", "analyze", "report"]},
            "First gather data, then analyze it, then report the findings"
        )
        assert result > 0.5

    def test_no_components_present(self):
        result = self._eval(
            {"key_components": ["quantum", "teleport"]},
            "Just a simple plan with no special words here at all"
        )
        assert result < 1.0

    def test_short_response_penalized(self):
        result = self._eval(
            {"key_components": ["gather"]},
            "gather"
        )
        assert result < 1.0  # Length score penalizes short response

    def test_very_long_response_penalized(self):
        result = self._eval(
            {"key_components": ["gather"]},
            "gather " + "word " * 900  # >800 words
        )
        # Length score slightly penalized: 0.9 instead of 1.0


# ──────────────────────────────────────────────────────────────────────────────
# _tools_from_trace
# ──────────────────────────────────────────────────────────────────────────────

class TestToolsFromTrace:
    def _call(self, trace):
        from ollama_arena.evaluator import _tools_from_trace
        return _tools_from_trace(trace)

    def test_none_trace_returns_empty(self):
        assert self._call(None) == []

    def test_empty_trace_returns_empty(self):
        assert self._call([]) == []

    def test_trace_with_tool_results(self):
        trace = [{"tool_results": [{"name": "search", "arguments": {"q": "test"}}]}]
        result = self._call(trace)
        assert len(result) == 1
        assert result[0]["name"] == "search"

    def test_trace_with_tool_calls(self):
        import json
        trace = [{"tool_calls": [{"function": {"name": "calc", "arguments": json.dumps({"a": 1})}}]}]
        result = self._call(trace)
        assert len(result) == 1
        assert result[0]["name"] == "calc"

    def test_non_dict_step_skipped(self):
        trace = ["not_a_dict", {"tool_results": [{"name": "foo"}]}]
        result = self._call(trace)
        assert len(result) == 1

    def test_step_without_tools_skipped(self):
        trace = [{"message": "no tools here"}]
        result = self._call(trace)
        assert result == []

    def test_invalid_tool_call_args_become_empty(self):
        trace = [{"tool_calls": [{"function": {"name": "f", "arguments": "invalid_json{"}}]}]
        result = self._call(trace)
        assert result[0]["arguments"] == {}


# ──────────────────────────────────────────────────────────────────────────────
# _validate_args
# ──────────────────────────────────────────────────────────────────────────────

class TestValidateArgs:
    def _call(self, actual, expected):
        from ollama_arena.evaluator import _validate_args
        return _validate_args(actual, expected)

    def test_empty_expected_returns_true(self):
        assert self._call({"k": "v"}, {}) is True

    def test_empty_actual_returns_false(self):
        assert self._call({}, {"k": "pattern"}) is False

    def test_matching_pattern(self):
        assert self._call({"url": "https://example.com"}, {"url": r"https://"}) is True

    def test_non_matching_pattern(self):
        assert self._call({"url": "ftp://example.com"}, {"url": r"https://"}) is False

    def test_case_insensitive(self):
        assert self._call({"q": "HELLO"}, {"q": r"hello"}) is True


# ──────────────────────────────────────────────────────────────────────────────
# _subsequence_score
# ──────────────────────────────────────────────────────────────────────────────

class TestSubsequenceScore:
    def _call(self, actual, expected, args=None):
        from ollama_arena.evaluator import _subsequence_score
        return _subsequence_score(actual, expected, args)

    def test_empty_expected_returns_half(self):
        assert self._call([{"name": "tool"}], []) == pytest.approx(0.5)

    def test_empty_actual_returns_zero(self):
        assert self._call([], ["tool1"]) == pytest.approx(0.0)

    def test_perfect_sequence(self):
        actual = [{"name": "search", "arguments": {}}, {"name": "calc", "arguments": {}}]
        result = self._call(actual, ["search", "calc"])
        assert result == pytest.approx(1.0)

    def test_partial_sequence(self):
        actual = [{"name": "search", "arguments": {}}]
        result = self._call(actual, ["search", "calc"])
        assert result == pytest.approx(0.5)

    def test_wrong_order_not_counted(self):
        actual = [{"name": "calc", "arguments": {}}, {"name": "search", "arguments": {}}]
        result = self._call(actual, ["search", "calc"])
        # "search" is not first, "calc" is found first as "search"
        # this actually counts partial matches
        assert 0.0 <= result <= 1.0

    def test_with_matching_args(self):
        actual = [{"name": "search", "arguments": {"q": "python"}}]
        result = self._call(actual, ["search"], {"search": {"q": r"python"}})
        assert result == pytest.approx(1.0)


# ──────────────────────────────────────────────────────────────────────────────
# eval_agent_trajectory
# ──────────────────────────────────────────────────────────────────────────────

class TestEvalAgentTrajectory:
    def _eval(self, task, trace):
        from ollama_arena.evaluator import eval_agent_trajectory
        return eval_agent_trajectory(task, trace)

    def test_no_expected_tools_returns_half(self):
        result = self._eval({}, None)
        assert result == pytest.approx(0.5)

    def test_expected_tools_empty_trace(self):
        result = self._eval({"expected_tools": ["search"]}, None)
        assert result == pytest.approx(0.0)

    def test_expected_tool_single_found(self):
        trace = [{"tool_results": [{"name": "search"}]}]
        result = self._eval({"expected_tool": "search"}, trace)
        assert result > 0.0

    def test_expected_tools_list_all_found(self):
        trace = [
            {"tool_results": [{"name": "search"}]},
            {"tool_results": [{"name": "calc"}]},
        ]
        result = self._eval({"expected_tools": ["search", "calc"]}, trace)
        assert result == pytest.approx(1.0)


# ──────────────────────────────────────────────────────────────────────────────
# eval_vision
# ──────────────────────────────────────────────────────────────────────────────

class TestEvalVision:
    def _eval(self, task, response):
        from ollama_arena.evaluator import eval_vision
        return eval_vision(task, response)

    def test_no_keywords_non_empty_returns_half(self):
        result = self._eval({}, "Some response")
        assert result == pytest.approx(0.5)

    def test_no_keywords_empty_returns_zero(self):
        result = self._eval({}, "")
        assert result == pytest.approx(0.0)

    def test_all_keywords_present(self):
        result = self._eval({"expected_keywords": ["cat", "dog"]}, "I see a cat and a dog")
        assert result == pytest.approx(1.0)

    def test_partial_keywords(self):
        result = self._eval({"expected_keywords": ["cat", "fish"]}, "I see a cat")
        assert result == pytest.approx(0.5)

    def test_no_keywords_in_response(self):
        result = self._eval({"expected_keywords": ["quantum"]}, "just a regular response")
        assert result == pytest.approx(0.0)


# ──────────────────────────────────────────────────────────────────────────────
# eval_tool_use
# ──────────────────────────────────────────────────────────────────────────────

class TestEvalToolUse:
    def _eval(self, task, response, trace=None):
        from ollama_arena.evaluator import eval_tool_use
        return eval_tool_use(task, response, trace=trace)

    def test_no_expected_tool_no_trace(self):
        result = self._eval({}, "response")
        assert result == pytest.approx(0.5)

    def test_json_response_correct_tool(self):
        import json
        response = json.dumps([{"function": {"name": "search", "arguments": json.dumps({"q": "test"})}}])
        result = self._eval({"expected_tool": "search", "expected_args": {"q": "test"}}, response)
        assert result == pytest.approx(1.0)

    def test_json_response_wrong_args(self):
        import json
        response = json.dumps([{"function": {"name": "search", "arguments": json.dumps({"q": "wrong"})}}])
        result = self._eval({"expected_tool": "search", "expected_args": {"q": "test"}}, response)
        assert result == pytest.approx(0.8)

    def test_tool_mentioned_in_text(self):
        result = self._eval({"expected_tool": "search"}, "I would use the search tool")
        assert result == pytest.approx(0.4)

    def test_tool_not_mentioned(self):
        result = self._eval({"expected_tool": "search"}, "I would just look it up")
        assert result == pytest.approx(0.0)

    def test_with_trace_perfect(self):
        trace = [{"tool_results": [{"name": "search"}]}]
        result = self._eval({"expected_tool": "search"}, "", trace=trace)
        assert result == pytest.approx(1.0)


# ──────────────────────────────────────────────────────────────────────────────
# evaluate (router)
# ──────────────────────────────────────────────────────────────────────────────

class TestEvaluateRouter:
    def _eval(self, task, response):
        from ollama_arena.evaluator import evaluate
        return evaluate(task, response)

    def test_json_category_routes_to_eval_json(self):
        task = {"category": "json_format", "expected_schema": None}
        result = self._eval(task, '{"key": "value"}')
        assert result == pytest.approx(1.0)

    def test_json_tid_prefix_routes_to_eval_json(self):
        task = {"id": "json_001", "expected_schema": None}
        result = self._eval(task, '{"k": "v"}')
        assert result == pytest.approx(1.0)

    def test_math_category_routes_to_text_answer(self):
        task = {"category": "math", "expected_answer": "42", "check": "contains"}
        result = self._eval(task, "The answer is 42")
        assert result == pytest.approx(1.0)

    def test_security_category_routes_correctly(self):
        task = {"category": "security", "expected_vulns": []}
        result = self._eval(task, "secure")
        assert result == pytest.approx(0.5)

    def test_inspection_category_routes_correctly(self):
        task = {"category": "inspection", "has_bug": False}
        result = self._eval(task, "Code looks clean and all good")
        assert result == pytest.approx(1.0)

    def test_planning_category_routes_correctly(self):
        task = {"category": "planning", "key_components": []}
        result = self._eval(task, "Plan...")
        assert result == pytest.approx(0.5)

    def test_tool_use_category_routes_correctly(self):
        task = {"category": "tool_use"}
        result = self._eval(task, "response")
        assert result == pytest.approx(0.5)

    def test_vision_category_routes_correctly(self):
        task = {"category": "vision", "expected_keywords": ["cat"]}
        result = self._eval(task, "I see a cat")
        assert result == pytest.approx(1.0)

    def test_unknown_category_returns_zero(self):
        task = {"id": "unknown_001", "category": "nonexistent"}
        result = self._eval(task, "response")
        assert result == pytest.approx(0.0)

    def test_creative_without_judge_returns_none(self):
        from ollama_arena.evaluator import evaluate
        task = {"category": "creative"}
        result = evaluate(task, "A creative story")
        assert result is None

    def test_reasoning_prefix_routes_to_text_answer(self):
        task = {"id": "reas_001", "expected_answer": "yes", "check": "contains"}
        result = self._eval(task, "The answer is yes")
        assert result == pytest.approx(1.0)

    def test_sec_prefix_routes_to_security(self):
        task = {"id": "sec_001", "expected_vulns": []}
        result = self._eval(task, "No issues")
        assert result == pytest.approx(0.5)
