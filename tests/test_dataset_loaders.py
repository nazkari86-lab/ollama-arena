"""Tests for datasets/loader.py — row normalizer functions."""
from __future__ import annotations

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# DatasetInfo dataclass
# ──────────────────────────────────────────────────────────────────────────────

class TestDatasetInfo:
    def test_defaults(self):
        from ollama_arena.datasets.loader import DatasetInfo
        d = DatasetInfo(name="test", hf_id="test/dataset")
        assert d.split == "test"
        assert d.category == "coding"
        assert d.n_tasks == 0

    def test_custom_values(self):
        from ollama_arena.datasets.loader import DatasetInfo
        d = DatasetInfo(name="gsm", hf_id="gsm8k", split="train", category="math", n_tasks=100)
        assert d.split == "train"
        assert d.n_tasks == 100


# ──────────────────────────────────────────────────────────────────────────────
# Normalizer functions
# ──────────────────────────────────────────────────────────────────────────────

class TestHumanEval:
    def _row(self):
        return {
            "task_id": "HumanEval/0",
            "prompt": "def add(a, b):\n",
            "test": "def check(candidate):\n    assert candidate(1, 2) == 3\n",
            "entry_point": "add",
            "canonical_solution": "return a + b",
        }

    def test_returns_dict(self):
        from ollama_arena.datasets.loader import _humaneval
        result = _humaneval(self._row(), 0)
        assert isinstance(result, dict)

    def test_category_is_coding(self):
        from ollama_arena.datasets.loader import _humaneval
        result = _humaneval(self._row(), 0)
        assert result["category"] == "coding"

    def test_id_includes_task_id(self):
        from ollama_arena.datasets.loader import _humaneval
        result = _humaneval(self._row(), 0)
        assert "0" in result["id"]

    def test_test_code_includes_check_call(self):
        from ollama_arena.datasets.loader import _humaneval
        result = _humaneval(self._row(), 0)
        assert "check(add)" in result["test_code"]

    def test_instruction_includes_prompt(self):
        from ollama_arena.datasets.loader import _humaneval
        result = _humaneval(self._row(), 0)
        assert "add" in result["instruction"]


class TestMBPP:
    def _row(self):
        return {
            "task_id": 1,
            "text": "Write a function to find the maximum of a list.",
            "code": "def max_list(lst): return max(lst)",
            "test_list": ["assert max_list([1,2,3]) == 3", "assert max_list([0]) == 0"],
        }

    def test_category_is_coding(self):
        from ollama_arena.datasets.loader import _mbpp
        result = _mbpp(self._row(), 0)
        assert result["category"] == "coding"

    def test_test_code_includes_tests(self):
        from ollama_arena.datasets.loader import _mbpp
        result = _mbpp(self._row(), 0)
        assert "assert max_list" in result["test_code"]

    def test_id_includes_task_id(self):
        from ollama_arena.datasets.loader import _mbpp
        result = _mbpp(self._row(), 0)
        assert "1" in result["id"]

    def test_instruction_includes_text(self):
        from ollama_arena.datasets.loader import _mbpp
        result = _mbpp(self._row(), 0)
        assert "maximum" in result["instruction"]


class TestGSM8K:
    def _row(self):
        return {
            "question": "If there are 5 apples and you eat 2, how many are left?",
            "answer": "You started with 5 apples. After eating 2, you have 5-2=3 apples.\n#### 3",
        }

    def test_category_is_math(self):
        from ollama_arena.datasets.loader import _gsm8k
        result = _gsm8k(self._row(), 0)
        assert result["category"] == "math"

    def test_final_answer_extracted(self):
        from ollama_arena.datasets.loader import _gsm8k
        result = _gsm8k(self._row(), 0)
        assert result["expected_answer"] == "3"

    def test_check_is_numeric_approx(self):
        from ollama_arena.datasets.loader import _gsm8k
        result = _gsm8k(self._row(), 0)
        assert result["check"] == "numeric_approx"

    def test_answer_without_hash_fallback(self):
        from ollama_arena.datasets.loader import _gsm8k
        row = {"question": "Q?", "answer": "The answer is 42"}
        result = _gsm8k(row, 0)
        assert "42" in result["expected_answer"] or len(result["expected_answer"]) > 0


class TestMMLU:
    def _row(self):
        return {
            "question": "What is the capital of France?",
            "choices": ["Berlin", "Paris", "London", "Rome"],
            "answer": 1,
            "subject": "geography",
        }

    def test_category_is_knowledge(self):
        from ollama_arena.datasets.loader import _mmlu
        result = _mmlu(self._row(), 0)
        assert result["category"] == "knowledge"

    def test_answer_letter_extracted(self):
        from ollama_arena.datasets.loader import _mmlu
        result = _mmlu(self._row(), 0)
        assert result["expected_answer"] == "B"

    def test_check_is_exact_prefix(self):
        from ollama_arena.datasets.loader import _mmlu
        result = _mmlu(self._row(), 0)
        assert result["check"] == "exact_prefix"

    def test_instruction_includes_choices(self):
        from ollama_arena.datasets.loader import _mmlu
        result = _mmlu(self._row(), 0)
        assert "Paris" in result["instruction"]


class TestBBH:
    def _row(self):
        return {"input": "Solve: 5 + 3 = ?", "target": "8"}

    def test_category_is_reasoning(self):
        from ollama_arena.datasets.loader import _bbh
        result = _bbh(self._row(), 0)
        assert result["category"] == "reasoning"

    def test_expected_answer(self):
        from ollama_arena.datasets.loader import _bbh
        result = _bbh(self._row(), 0)
        assert result["expected_answer"] == "8"

    def test_difficulty_hard(self):
        from ollama_arena.datasets.loader import _bbh
        result = _bbh(self._row(), 0)
        assert result["difficulty"] == "hard"


class TestMultiplE:
    def _row(self):
        return {
            "name": "test_0",
            "language": "py",
            "prompt": "def add(a, b):\n",
            "tests": "assert add(1,2) == 3",
            "stop_tokens": ["\nclass"],
        }

    def test_category_is_coding(self):
        from ollama_arena.datasets.loader import _multipl_e
        result = _multipl_e(self._row(), 0)
        assert result["category"] == "coding"

    def test_language_py_mapped_to_python(self):
        from ollama_arena.datasets.loader import _multipl_e
        result = _multipl_e(self._row(), 0)
        assert result["language"] == "python"

    def test_language_js_mapped(self):
        from ollama_arena.datasets.loader import _multipl_e
        row = dict(self._row())
        row["language"] = "js"
        result = _multipl_e(row, 0)
        assert result["language"] == "javascript"

    def test_unknown_language_passthrough(self):
        from ollama_arena.datasets.loader import _multipl_e
        row = dict(self._row())
        row["language"] = "lua"
        result = _multipl_e(row, 0)
        assert result["language"] == "lua"


class TestHellaswag:
    def _row(self):
        return {
            "ctx": "A man is walking down the street.",
            "endings": ["He stops for coffee", "He flies away", "He melts", "He talks"],
            "label": "0",
        }

    def test_category_is_reasoning(self):
        from ollama_arena.datasets.loader import _hellaswag
        result = _hellaswag(self._row(), 0)
        assert result["category"] == "reasoning"

    def test_answer_is_letter(self):
        from ollama_arena.datasets.loader import _hellaswag
        result = _hellaswag(self._row(), 0)
        assert result["expected_answer"] == "A"

    def test_instruction_includes_options(self):
        from ollama_arena.datasets.loader import _hellaswag
        result = _hellaswag(self._row(), 0)
        assert "A." in result["instruction"]


class TestTruthfulQA:
    def _row(self):
        return {
            "question": "What is the boiling point of water?",
            "best_answer": "100 degrees Celsius at sea level",
        }

    def test_category_is_knowledge(self):
        from ollama_arena.datasets.loader import _truthfulqa
        result = _truthfulqa(self._row(), 0)
        assert result["category"] == "knowledge"

    def test_expected_answer_set(self):
        from ollama_arena.datasets.loader import _truthfulqa
        result = _truthfulqa(self._row(), 0)
        assert "100" in result["expected_answer"]

    def test_check_is_contains(self):
        from ollama_arena.datasets.loader import _truthfulqa
        result = _truthfulqa(self._row(), 0)
        assert result["check"] == "contains"


class TestARC:
    def _row(self):
        return {
            "question": "Which is a mammal?",
            "choices": {"text": ["Fish", "Dog", "Insect", "Bird"], "label": ["A", "B", "C", "D"]},
            "answerKey": "B",
            "id": "arc_001",
        }

    def test_category_is_knowledge(self):
        from ollama_arena.datasets.loader import _arc
        result = _arc(self._row(), 0)
        assert result["category"] == "knowledge"

    def test_answer_letter(self):
        from ollama_arena.datasets.loader import _arc
        result = _arc(self._row(), 0)
        assert result["expected_answer"] == "B"

    def test_instruction_includes_options(self):
        from ollama_arena.datasets.loader import _arc
        result = _arc(self._row(), 0)
        assert "Dog" in result["instruction"]


class TestLivecode:
    def _row(self):
        return {
            "question_id": 42,
            "question_content": "Write a function to add two numbers.",
            "starter_code": "def add(a, b):\n    pass",
            "public_test_cases": '[{"input": "1 2", "output": "3"}]',
            "difficulty": "easy",
        }

    def test_category_is_coding(self):
        from ollama_arena.datasets.loader import _livecode
        result = _livecode(self._row(), 0)
        assert result["category"] == "coding"

    def test_invalid_json_test_cases(self):
        from ollama_arena.datasets.loader import _livecode
        row = dict(self._row())
        row["public_test_cases"] = "not valid json"
        result = _livecode(row, 0)
        assert result["test_code"] == ""


class TestMath500:
    def _row(self):
        return {
            "problem": "Find the value of x where 2x = 10.",
            "solution": "We solve: 2x = 10, so x = \\boxed{5}.",
            "level": "Level 2",
        }

    def test_category_is_math(self):
        from ollama_arena.datasets.loader import _math500
        result = _math500(self._row(), 0)
        assert result["category"] == "math"

    def test_answer_extracted_from_boxed(self):
        from ollama_arena.datasets.loader import _math500
        result = _math500(self._row(), 0)
        assert result["expected_answer"] == "5"

    def test_check_is_numeric_approx(self):
        from ollama_arena.datasets.loader import _math500
        result = _math500(self._row(), 0)
        assert result["check"] == "numeric_approx"

    def test_fallback_when_no_boxed(self):
        from ollama_arena.datasets.loader import _math500
        row = {"problem": "Q", "solution": "The answer is x = 42", "level": "Level 1"}
        result = _math500(row, 0)
        assert len(result["expected_answer"]) > 0
