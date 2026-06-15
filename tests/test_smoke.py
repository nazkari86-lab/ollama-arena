"""Smoke tests that don't need an LLM backend running."""
from __future__ import annotations
import tempfile, os

from ollama_arena import (
    Arena, EloStore, get_tasks, task_stats, list_categories, list_languages,
)
from ollama_arena.elo import update_elo
from ollama_arena.evaluator import evaluate, extract_code
from ollama_arena.sandboxes import run_in_language, available_languages
from ollama_arena.backends import (
    OllamaBackend, OpenAICompatBackend, auto_backend, detect_backend,
)


def test_elo_math():
    a, b = update_elo(1200, 1200, 1.0)
    assert a > 1200 and b < 1200
    assert round(a + b, 2) == 2400.0   # zero-sum


def test_elo_store_persists():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "x.db")
        s = EloStore(db_path=db)
        s.record_match("m1", "m2", "coding", 1.0, 0.0)
        s.record_match("m1", "m2", "coding", 1.0, 0.0)
        board = s.leaderboard()
        assert board[0]["model"] == "m1"
        assert board[0]["wins"] == 2
        # reload
        s2 = EloStore(db_path=db)
        assert s2.leaderboard()[0]["model"] == "m1"


def test_task_stats():
    stats = task_stats()
    assert sum(stats.values()) > 50
    assert "coding" in stats and "reasoning" in stats


def test_get_tasks_filters():
    py = get_tasks(category="coding", language="python")
    js = get_tasks(category="coding", language="javascript")
    rust = get_tasks(category="coding", language="rust")
    assert all(t.get("language", "python") == "python" for t in py)
    assert all(t["language"] == "javascript" for t in js)
    assert all(t["language"] == "rust" for t in rust)


def test_languages_list():
    langs = list_languages()
    assert "python" in langs
    assert "javascript" in langs


def test_extract_code_python():
    body = "Here's the code:\n```python\ndef f(): return 42\n```\nthanks."
    assert extract_code(body, "python") == "def f(): return 42"


def test_eval_coding_pass():
    task = {"id":"code_x","category":"coding","language":"python",
            "test_code":"assert f()==42"}
    score = evaluate(task, "def f(): return 42")
    assert score == 1.0


def test_eval_coding_fail():
    task = {"id":"code_x","category":"coding","language":"python",
            "test_code":"assert f()==42"}
    assert evaluate(task, "def f(): return 0") == 0.0


def test_reasoning_eval():
    task = {"id":"reas_1","category":"reasoning",
            "expected_answer":"yes","check":"exact_prefix"}
    assert evaluate(task, "yes, because of XYZ.") == 1.0
    assert evaluate(task, "no, this is wrong.") == 0.0


def test_numeric_approx():
    task = {"id":"gsm8k_1","category":"math",
            "expected_answer":"42","check":"numeric_approx","tolerance":0}
    assert evaluate(task, "The answer is 42.") == 1.0
    assert evaluate(task, "It is 40.") == 0.0


def test_available_languages():
    langs = available_languages()
    assert "python" in langs
    assert "bash" in langs


def test_python_sandbox():
    r = run_in_language("print(2+2)", language="python")
    assert r.accepted
    assert "4" in r.output


def test_bash_sandbox():
    r = run_in_language("echo hello", language="bash")
    assert r.accepted
    assert "hello" in r.output


def test_blocked_pattern():
    r = run_in_language("import os; os.system('rm -rf /')", language="python")
    assert r.blocked


def test_backend_detection():
    assert detect_backend("http://localhost:11434") == "ollama"
    assert detect_backend("http://localhost:8000/v1") == "openai-compat"
    assert detect_backend("http://localhost:1234/v1") == "openai-compat"


def test_auto_backend_returns():
    b = auto_backend()
    assert b.name == "ollama"
    b2 = auto_backend("http://localhost:8000/v1")
    assert b2.name == "openai-compat"
    b3 = auto_backend("lmstudio")
    assert b3.name == "openai-compat"


def test_arena_construct_without_ollama():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "x.db")
        a = Arena(db_path=db)
        assert a.leaderboard() == []
