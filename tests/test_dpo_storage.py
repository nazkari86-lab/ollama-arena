"""Tests for DPO DatasetStorage — pure file I/O, no database required."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def _make_pair(**kw):
    from ollama_arena.finetuning.dpo_pipeline import DPOPair
    defaults = dict(
        prompt="Write hello world",
        chosen="print('Hello, World!')",
        rejected="puts 'Hello, World!'",
        chosen_model="llama3:8b",
        rejected_model="phi3:3b",
        category="coding",
        task_id="t1",
        elo_gap=30.0,
        match_id=1,
    )
    defaults.update(kw)
    return DPOPair(**defaults)


class TestDatasetStorage:
    def _make(self, tmp_path):
        from ollama_arena.finetuning.dpo_pipeline import DatasetStorage
        return DatasetStorage(base_dir=str(tmp_path / "dpo"))

    def test_init_creates_directory(self, tmp_path):
        s = self._make(tmp_path)
        assert s.base_dir.exists()

    def test_init_empty_index(self, tmp_path):
        s = self._make(tmp_path)
        assert s._index == {}

    def test_store_dataset_returns_version(self, tmp_path):
        from ollama_arena.finetuning.dpo_pipeline import DatasetVersion
        s = self._make(tmp_path)
        pairs = [_make_pair()]
        version = s.store_dataset(pairs, "llama3:8b", "phi3:3b", "coding")
        assert isinstance(version, DatasetVersion)

    def test_store_dataset_sets_num_pairs(self, tmp_path):
        s = self._make(tmp_path)
        pairs = [_make_pair(), _make_pair(task_id="t2", match_id=2)]
        version = s.store_dataset(pairs, "a", "b", "coding")
        assert version.num_pairs == 2

    def test_store_dataset_sets_category(self, tmp_path):
        s = self._make(tmp_path)
        version = s.store_dataset([_make_pair()], "a", "b", "math")
        assert version.category == "math"

    def test_store_creates_file(self, tmp_path):
        s = self._make(tmp_path)
        version = s.store_dataset([_make_pair()], "a", "b", "coding")
        assert Path(version.file_path).exists()

    def test_store_file_is_jsonl(self, tmp_path):
        s = self._make(tmp_path)
        version = s.store_dataset([_make_pair()], "a", "b", "coding")
        with open(version.file_path) as f:
            data = json.loads(f.readline())
        assert "prompt" in data
        assert "chosen" in data
        assert "rejected" in data

    def test_store_updates_index(self, tmp_path):
        s = self._make(tmp_path)
        version = s.store_dataset([_make_pair()], "a", "b", "coding")
        assert version.version_id in s._index

    def test_load_returns_pairs(self, tmp_path):
        s = self._make(tmp_path)
        original = [_make_pair(prompt="Q1"), _make_pair(prompt="Q2", task_id="t2", match_id=2)]
        version = s.store_dataset(original, "a", "b", "coding")
        loaded = s.load_dataset(version.version_id)
        assert loaded is not None
        assert len(loaded) == 2

    def test_load_preserves_fields(self, tmp_path):
        s = self._make(tmp_path)
        version = s.store_dataset([_make_pair(prompt="Test prompt")], "a", "b", "coding")
        loaded = s.load_dataset(version.version_id)
        assert loaded[0].prompt == "Test prompt"
        assert loaded[0].chosen_model == "llama3:8b"

    def test_load_nonexistent_returns_none(self, tmp_path):
        s = self._make(tmp_path)
        assert s.load_dataset("nonexistent_id") is None

    def test_list_versions_empty(self, tmp_path):
        s = self._make(tmp_path)
        assert s.list_versions() == []

    def test_list_versions_returns_all(self, tmp_path):
        s = self._make(tmp_path)
        s.store_dataset([_make_pair()], "a", "b", "coding")
        s.store_dataset([_make_pair(task_id="t2", match_id=2)], "a", "b", "math")
        versions = s.list_versions()
        assert len(versions) == 2

    def test_list_versions_filter_by_category(self, tmp_path):
        s = self._make(tmp_path)
        s.store_dataset([_make_pair()], "a", "b", "coding")
        s.store_dataset([_make_pair(task_id="t2", match_id=2)], "a", "b", "math")
        coding = s.list_versions(category="coding")
        assert len(coding) == 1
        assert coding[0].category == "coding"

    def test_list_versions_filter_by_model(self, tmp_path):
        s = self._make(tmp_path)
        s.store_dataset([_make_pair()], "a", "llama3:8b", "coding")
        s.store_dataset([_make_pair(task_id="t2", match_id=2)], "a", "phi3:3b", "coding")
        result = s.list_versions(target_model="llama3:8b")
        assert len(result) == 1

    def test_compute_hash_deterministic(self, tmp_path):
        s = self._make(tmp_path)
        p1 = [_make_pair()]
        h1 = s._compute_hash(p1)
        h2 = s._compute_hash(p1)
        assert h1 == h2

    def test_compute_hash_different_pairs_differ(self, tmp_path):
        s = self._make(tmp_path)
        h1 = s._compute_hash([_make_pair(prompt="A")])
        h2 = s._compute_hash([_make_pair(prompt="B")])
        assert h1 != h2

    def test_compute_hash_empty_list(self, tmp_path):
        s = self._make(tmp_path)
        h = s._compute_hash([])
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex

    def test_elo_gap_stats_computed(self, tmp_path):
        s = self._make(tmp_path)
        pairs = [_make_pair(elo_gap=10.0), _make_pair(task_id="t2", match_id=2, elo_gap=30.0)]
        version = s.store_dataset(pairs, "a", "b", "coding")
        assert version.min_elo_gap == 10.0
        assert version.avg_elo_gap == 20.0

    def test_index_persisted_to_disk(self, tmp_path):
        s = self._make(tmp_path)
        s.store_dataset([_make_pair()], "a", "b", "coding")

        # Reload from disk
        from ollama_arena.finetuning.dpo_pipeline import DatasetStorage
        s2 = DatasetStorage(base_dir=str(tmp_path / "dpo"))
        assert len(s2._index) == 1

    def test_store_dataset_category_path_traversal_contained(self, tmp_path):
        """Regression test: category/target_model flowed unsanitized into the
        dataset filename, so a category like '../../evil' could make the
        written file escape base_dir entirely (path traversal on write)."""
        import os
        s = self._make(tmp_path)
        version = s.store_dataset(
            [_make_pair()], "a", "../../evil-model", "../../evil-category"
        )
        abs_file = os.path.abspath(version.file_path)
        abs_base = os.path.abspath(s.base_dir)
        assert os.path.commonpath([abs_file, abs_base]) == abs_base
        assert Path(version.file_path).exists()

    def test_store_dataset_path_separator_in_category_contained(self, tmp_path):
        import os
        s = self._make(tmp_path)
        version = s.store_dataset([_make_pair()], "a", "b", "coding/../../escape")
        abs_file = os.path.abspath(version.file_path)
        abs_base = os.path.abspath(s.base_dir)
        assert os.path.commonpath([abs_file, abs_base]) == abs_base
