from ollama_arena.datasets.loader import available_datasets


def test_new_datasets_registered():
    names = [d["name"] for d in available_datasets()]
    assert "livecode" in names,      "livecode missing"
    assert "math500" in names,       "math500 missing"
    assert "gpqa_diamond" in names,  "gpqa_diamond missing"
    assert "ifeval" in names,        "ifeval missing"
    assert "bigcodebench" in names,  "bigcodebench missing"


def test_livecode_schema():
    from ollama_arena.datasets.loader import _livecode
    raw = {"question_content": "Write fib(n)", "starter_code": "def fib(n):\n    pass",
           "public_test_cases": '[{"input": "1", "output": "1"}]',
           "difficulty": "easy", "question_id": "lc_001"}
    task = _livecode(raw)
    assert task["category"] == "coding"
    assert "fib" in task["instruction"]
    assert task["id"].startswith("livecode_")


def test_math500_schema():
    from ollama_arena.datasets.loader import _math500
    raw = {"problem": "What is 2+2?", "solution": "The answer is $\\boxed{4}$.",
           "level": "Level 1", "type": "Arithmetic"}
    task = _math500(raw)
    assert task["category"] == "math"
    assert task["expected_answer"] == "4"
    assert task["check"] == "numeric_approx"


def test_gpqa_schema():
    from ollama_arena.datasets.loader import _gpqa_diamond
    raw = {"Question": "Which enzyme catalyzes ATP synthesis?",
           "Correct Answer": "ATP synthase",
           "Explanation": "...", "Subdomain": "Biochemistry",
           "Record ID": "gpqa_001"}
    task = _gpqa_diamond(raw)
    assert task["category"] == "knowledge"
    assert "ATP synthase" in task["check_items"]


def test_ifeval_schema():
    from ollama_arena.datasets.loader import _ifeval
    raw = {"prompt": "Write a 50-word paragraph about cats.",
           "instruction_id_list": ["length_constraints:number_words"],
           "kwargs": [{"num_words": 50}],
           "key": 42}
    task = _ifeval(raw)
    assert task["category"] == "reasoning"
    assert task["use_judge"] is True


def test_bigcodebench_schema():
    from ollama_arena.datasets.loader import _bigcodebench
    raw = {"task_id": "BigCodeBench/0", "entry_point": "solve",
           "prompt": "Write a function solve(n) that returns n*2.",
           "test": "assert solve(3) == 6",
           "libs": ["math"]}
    task = _bigcodebench(raw)
    assert task["category"] == "coding"
    assert "solve" in task["instruction"]
    assert task["test_code"] == "assert solve(3) == 6"
