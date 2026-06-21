"""Tests for adversarial_gen — TaskDifficultyAnalyzer and AdversarialGenerator pure paths."""
from __future__ import annotations

import sqlite3
import os
import pytest


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _create_test_db(tmp_path):
    """Create a minimal arena DB with match_log and task_detail tables."""
    db_path = str(tmp_path / "test_arena.db")
    with sqlite3.connect(db_path) as cx:
        cx.execute("""
            CREATE TABLE IF NOT EXISTS match_log (
                id INTEGER PRIMARY KEY,
                model_a TEXT,
                model_b TEXT,
                outcome TEXT,
                category TEXT,
                created_at TEXT
            )
        """)
        cx.execute("""
            CREATE TABLE IF NOT EXISTS task_detail (
                id INTEGER PRIMARY KEY,
                match_id INTEGER,
                task_id TEXT,
                instruction TEXT,
                category TEXT,
                difficulty TEXT,
                outcome TEXT
            )
        """)
        cx.commit()
    return db_path


def _populate_db(db_path, matches, tasks):
    with sqlite3.connect(db_path) as cx:
        for m in matches:
            cx.execute(
                "INSERT INTO match_log (id, model_a, model_b, outcome, category) VALUES (?,?,?,?,?)",
                m,
            )
        for t in tasks:
            cx.execute(
                "INSERT INTO task_detail (match_id, task_id, instruction, category, difficulty, outcome) VALUES (?,?,?,?,?,?)",
                t,
            )
        cx.commit()


# ──────────────────────────────────────────────────────────────────────────────
# TaskDifficultyAnalyzer
# ──────────────────────────────────────────────────────────────────────────────

class TestTaskDifficultyAnalyzer:
    def _make(self, db_path):
        from ollama_arena.finetuning.adversarial_gen import TaskDifficultyAnalyzer
        return TaskDifficultyAnalyzer(db_path=db_path)

    def test_init_stores_db_path(self, tmp_path):
        db_path = str(tmp_path / "a.db")
        a = self._make(db_path)
        assert a.db_path == db_path

    def test_analyze_empty_db_returns_zeros(self, tmp_path):
        db_path = _create_test_db(tmp_path)
        a = self._make(db_path)
        result = a.analyze_difficulty_distribution()
        assert result["total_tasks"] == 0
        assert result["avg_win_rate"] == 0.0

    def test_analyze_returns_dict_keys(self, tmp_path):
        db_path = _create_test_db(tmp_path)
        a = self._make(db_path)
        result = a.analyze_difficulty_distribution()
        assert "distribution" in result
        assert "total_tasks" in result
        assert "avg_win_rate" in result

    def test_analyze_with_data(self, tmp_path):
        db_path = _create_test_db(tmp_path)
        _populate_db(
            db_path,
            matches=[(1, "llama3:8b", "phi3:3b", "a_wins", "coding")],
            tasks=[(1, "task_001", "Write hello world", "coding", "easy", "a_wins")],
        )
        a = self._make(db_path)
        result = a.analyze_difficulty_distribution()
        assert result["total_tasks"] == 1

    def test_analyze_nonexistent_db_returns_safe_result(self, tmp_path):
        a = self._make(str(tmp_path / "nonexistent.db"))
        result = a.analyze_difficulty_distribution()
        assert result["total_tasks"] == 0

    def test_find_too_easy_tasks_empty_db(self, tmp_path):
        db_path = _create_test_db(tmp_path)
        a = self._make(db_path)
        result = a.find_too_easy_tasks("llama3:8b")
        assert result == []

    def test_identify_weaknesses_empty_db(self, tmp_path):
        db_path = _create_test_db(tmp_path)
        a = self._make(db_path)
        result = a.identify_weaknesses("llama3:8b")
        assert isinstance(result, list)

    def test_find_too_easy_tasks_with_category(self, tmp_path):
        db_path = _create_test_db(tmp_path)
        a = self._make(db_path)
        result = a.find_too_easy_tasks("llama3:8b", category="coding")
        assert isinstance(result, list)


# ──────────────────────────────────────────────────────────────────────────────
# AdversarialGenerator — pure / fallback paths (no actual AI backend needed)
# ──────────────────────────────────────────────────────────────────────────────

class TestAdversarialGeneratorPurePaths:
    def _make(self, db_path):
        """Build an AdversarialGenerator with a stub backend."""
        from unittest.mock import MagicMock
        from ollama_arena.finetuning.adversarial_gen import AdversarialGenerator
        stub = MagicMock()
        # Simulate a failed backend call so fallback kicks in
        result_mock = MagicMock()
        result_mock.ok = False
        result_mock.text = ""
        stub.generate.return_value = result_mock
        return AdversarialGenerator(db_path=db_path, backend=stub)

    def test_add_complexity_manually_appends_text(self, tmp_path):
        db_path = _create_test_db(tmp_path)
        gen = self._make(db_path)
        original = "Write a function that sorts a list."
        result = gen._add_complexity_manually(original)
        assert result.startswith(original)
        assert len(result) > len(original)

    def test_add_complexity_manually_deterministic(self, tmp_path):
        db_path = _create_test_db(tmp_path)
        gen = self._make(db_path)
        instruction = "Implement binary search."
        r1 = gen._add_complexity_manually(instruction)
        r2 = gen._add_complexity_manually(instruction)
        assert r1 == r2

    def test_generate_harder_variant_fallback(self, tmp_path):
        from ollama_arena.finetuning.adversarial_gen import AdversarialTask, DifficultyLevel
        db_path = _create_test_db(tmp_path)
        gen = self._make(db_path)
        base_task = {
            "task_id": "t1",
            "instruction": "Sort a list.",
            "category": "coding",
            "difficulty": "easy",
        }
        result = gen.generate_harder_variant(base_task)
        assert isinstance(result, AdversarialTask)
        assert result.difficulty in list(DifficultyLevel)
        assert result.task_id.startswith("adv_")

    def test_generate_harder_variant_difficulty_increases(self, tmp_path):
        from ollama_arena.finetuning.adversarial_gen import DifficultyLevel
        db_path = _create_test_db(tmp_path)
        gen = self._make(db_path)
        base = {"task_id": "t1", "instruction": "Solve.", "category": "math", "difficulty": "easy"}
        result = gen.generate_harder_variant(base, difficulty_increase=1)
        assert result.difficulty != DifficultyLevel.EASY

    def test_generate_harder_variant_expert_stays_expert(self, tmp_path):
        from ollama_arena.finetuning.adversarial_gen import DifficultyLevel
        db_path = _create_test_db(tmp_path)
        gen = self._make(db_path)
        base = {"task_id": "t1", "instruction": "Solve.", "category": "math", "difficulty": "expert"}
        result = gen.generate_harder_variant(base, difficulty_increase=5)
        assert result.difficulty == DifficultyLevel.EXPERT

    def test_generate_harder_variant_unknown_difficulty_defaults(self, tmp_path):
        from ollama_arena.finetuning.adversarial_gen import AdversarialTask
        db_path = _create_test_db(tmp_path)
        gen = self._make(db_path)
        base = {"task_id": "t1", "instruction": "Solve.", "category": "math", "difficulty": "???"}
        result = gen.generate_harder_variant(base)
        assert isinstance(result, AdversarialTask)

    def test_generate_harder_variant_backend_raises_no_crash(self, tmp_path):
        """Regression test: generate_harder_variant used to crash with
        UnboundLocalError when self.backend.generate() raised, because the
        except-block fallback never assigned `result`, but the metadata dict
        afterward unconditionally read `result.ok`. Should fall back cleanly."""
        from unittest.mock import MagicMock
        from ollama_arena.finetuning.adversarial_gen import AdversarialGenerator, AdversarialTask

        db_path = _create_test_db(tmp_path)
        backend = MagicMock()
        backend.generate.side_effect = RuntimeError("backend unavailable")
        gen = AdversarialGenerator(db_path=db_path, backend=backend)

        base_task = {
            "task_id": "t1",
            "instruction": "Sort a list.",
            "category": "coding",
            "difficulty": "medium",
        }
        result = gen.generate_harder_variant(base_task)
        assert isinstance(result, AdversarialTask)
        assert result.metadata["generation_method"] == "manual"

    def test_generate_for_weakness_empty_db_returns_empty(self, tmp_path):
        from ollama_arena.finetuning.adversarial_gen import WeaknessTarget
        db_path = _create_test_db(tmp_path)
        gen = self._make(db_path)
        weakness = WeaknessTarget(
            model="llama3:8b",
            category="coding",
            subcategory=None,
            win_rate=0.4,
            sample_count=10,
            gap_to_target=0.2,
            priority=0.8,
        )
        result = gen.generate_for_weakness(weakness, num_tasks=5)
        assert isinstance(result, list)
        assert len(result) == 0  # No base tasks in empty DB


# ──────────────────────────────────────────────────────────────────────────────
# generate_harder_tasks convenience function
# ──────────────────────────────────────────────────────────────────────────────

class TestGenerateHarderTasksFunction:
    def test_returns_tuple(self, tmp_path):
        from unittest.mock import MagicMock, patch
        from ollama_arena.finetuning import adversarial_gen

        db_path = _create_test_db(tmp_path)
        mock_gen = MagicMock()
        mock_gen.generate_adversarial_dataset.return_value = []
        mock_gen.save_adversarial_tasks.return_value = "/tmp/out.jsonl"

        with patch.object(adversarial_gen, "AdversarialGenerator", return_value=mock_gen):
            tasks, path = adversarial_gen.generate_harder_tasks(
                model="llama3:8b",
                db_path=db_path,
                num_tasks=3,
            )
        assert isinstance(tasks, list)
        assert isinstance(path, str)
