import os
import sqlite3
import tempfile
from unittest.mock import MagicMock

import pytest

from ollama_arena.finetune.analyzer import analyze_task_failures
from ollama_arena.finetune.generator import build_training_dataset, build_dpo_dataset
from ollama_arena.backends.base import GenResult


def _seed_arena_db(path: str):
    with sqlite3.connect(path) as cx:
        cx.executescript("""
            CREATE TABLE match_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_a TEXT, model_b TEXT, category TEXT,
                score_a REAL, score_b REAL,
                elo_a_after REAL, elo_b_after REAL
            );
            CREATE TABLE task_detail (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER, task_id TEXT, category TEXT,
                instruction TEXT, response_a TEXT, response_b TEXT,
                score_a REAL, score_b REAL, outcome TEXT
            );
        """)
        cx.execute(
            "INSERT INTO match_log (model_a, model_b, category, score_a, score_b, "
            "elo_a_after, elo_b_after) VALUES (?,?,?,?,?,?,?)",
            ("weak:7b", "strong:70b", "coding", 0.2, 0.9, 1000, 1200),
        )
        match_id = cx.execute("SELECT last_insert_rowid()").fetchone()[0]
        cx.execute(
            "INSERT INTO task_detail (match_id, task_id, category, instruction, "
            "response_a, response_b, score_a, score_b, outcome) VALUES (?,?,?,?,?,?,?,?,?)",
            (match_id, "code_001", "coding", "Write hello world",
             "bad code", "print('hello')", 0.1, 1.0, "b_wins"),
        )


class _FakeBackend:
    name = "fake"

    def generate(self, model, prompt, **kwargs):
        return GenResult(text=f"teacher answer for {model}", model=model)


def test_analyze_task_failures_finds_weak_model():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "arena.db")
        _seed_arena_db(db)
        failures = analyze_task_failures(db, model="weak:7b", category="coding")
        assert len(failures) == 1
        assert failures[0]["task_id"] == "code_001"
        assert failures[0]["avg_score"] < 0.5


def test_build_training_dataset_uses_failed_tasks():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "arena.db")
        _seed_arena_db(db)
        ds = build_training_dataset(
            weak_model="weak:7b",
            category="coding",
            db_path=db,
            teacher_model="strong:70b",
            backend=_FakeBackend(),
            n_tasks=5,
        )
        assert len(ds) == 1
        assert ds[0]["task_id"] == "code_001"
        assert "teacher answer" in ds[0]["output"]


def test_build_dpo_dataset_creates_preference_pairs():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "arena.db")
        _seed_arena_db(db)
        ds = build_dpo_dataset(
            weak_model="weak:7b",
            category="coding",
            db_path=db,
            teacher_model="strong:70b",
            backend=_FakeBackend(),
            n_tasks=5,
        )
        assert len(ds) == 1
        assert ds[0]["chosen"]
        assert ds[0]["rejected"] == "bad code"
        assert ds[0]["prompt"] == "Write hello world"
