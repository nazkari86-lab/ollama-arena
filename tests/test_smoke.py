from __future__ import annotations
import os
import tempfile

from ollama_arena import (
    Arena, EloStore,
    get_tasks, task_stats, list_categories, list_languages,
)
from ollama_arena.elo import update_elo
from ollama_arena.evaluator import evaluate, extract_code
from ollama_arena.sandboxes import run_in_language, available_languages
from ollama_arena.backends import (
    OllamaBackend, OpenAICompatBackend, auto_backend, detect_backend,
)


def test_elo_zero_sum():
    a, b = update_elo(1200, 1200, 1.0)
    assert a > 1200 and b < 1200
    assert round(a + b, 2) == 2400.0


def test_elo_store_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "x.db")
        s = EloStore(db_path=db)
        s.record_match("m1", "m2", "coding", 1.0, 0.0)
        s.record_match("m1", "m2", "coding", 1.0, 0.0)
        assert s.leaderboard()[0]["model"] == "m1"
        assert s.leaderboard()[0]["wins"] == 2
        # reload from disk
        assert EloStore(db_path=db).leaderboard()[0]["model"] == "m1"


def test_task_stats():
    s = task_stats()
    assert sum(s.values()) > 50
    assert {"coding", "reasoning"} <= s.keys()


def test_get_tasks_language_filter():
    assert all(t.get("language", "python") == "python"
               for t in get_tasks(category="coding", language="python"))
    js = get_tasks(category="coding", language="javascript")
    assert js and all(t["language"] == "javascript" for t in js)


def test_languages_list():
    langs = list_languages()
    assert "python" in langs and "javascript" in langs


def test_extract_code():
    body = "Here:\n```python\ndef f(): return 42\n```\nthanks."
    assert extract_code(body, "python") == "def f(): return 42"


def test_eval_coding_passes():
    task = {"id": "code_x", "category": "coding", "language": "python",
            "test_code": "assert f()==42"}
    assert evaluate(task, "def f(): return 42") == 1.0


def test_eval_coding_fails():
    task = {"id": "code_x", "category": "coding", "language": "python",
            "test_code": "assert f()==42"}
    assert evaluate(task, "def f(): return 0") == 0.0


def test_eval_reasoning_prefix():
    task = {"id": "reas_1", "category": "reasoning",
            "expected_answer": "yes", "check": "exact_prefix"}
    assert evaluate(task, "yes, because of XYZ.") == 1.0
    assert evaluate(task, "no, this is wrong.") == 0.0


def test_eval_numeric_approx():
    task = {"id": "gsm8k_1", "category": "math",
            "expected_answer": "42", "check": "numeric_approx", "tolerance": 0}
    assert evaluate(task, "The answer is 42.") == 1.0
    assert evaluate(task, "It is 40.") == 0.0


def test_available_languages_has_python_and_bash():
    langs = available_languages()
    assert "python" in langs and "bash" in langs


def test_python_sandbox():
    r = run_in_language("print(2+2)", language="python")
    assert r.accepted and "4" in r.output


def test_bash_sandbox():
    r = run_in_language("echo hello", language="bash")
    assert r.accepted and "hello" in r.output


def test_sandbox_blocks_rm_rf():
    r = run_in_language("import os; os.system('rm -rf /')", language="python")
    assert r.blocked


def test_detect_backend():
    assert detect_backend("http://localhost:11434") == "ollama"
    assert detect_backend("http://localhost:8000/v1") == "openai-compat"
    assert detect_backend("http://localhost:1234/v1") == "openai-compat"


def test_auto_backend_picks_right_type():
    assert auto_backend().name == "ollama"
    assert auto_backend("http://localhost:8000/v1").name == "openai-compat"
    assert auto_backend("lmstudio").name == "openai-compat"


def test_arena_constructs_offline():
    with tempfile.TemporaryDirectory() as tmp:
        a = Arena(db_path=os.path.join(tmp, "x.db"))
        assert a.leaderboard() == []
