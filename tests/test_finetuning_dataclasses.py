"""Tests for finetuning module — dataclasses, enums and pure functions."""
from __future__ import annotations

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# adversarial_gen — DifficultyLevel, WeaknessTarget, AdversarialTask
# ──────────────────────────────────────────────────────────────────────────────

class TestDifficultyLevel:
    def test_all_values(self):
        from ollama_arena.finetuning.adversarial_gen import DifficultyLevel
        assert DifficultyLevel.EASY.value == "easy"
        assert DifficultyLevel.MEDIUM.value == "medium"
        assert DifficultyLevel.HARD.value == "hard"
        assert DifficultyLevel.EXPERT.value == "expert"

    def test_from_value(self):
        from ollama_arena.finetuning.adversarial_gen import DifficultyLevel
        assert DifficultyLevel("hard") == DifficultyLevel.HARD

    def test_enum_length(self):
        from ollama_arena.finetuning.adversarial_gen import DifficultyLevel
        assert len(list(DifficultyLevel)) == 4


class TestWeaknessTarget:
    def _make(self, **kw):
        from ollama_arena.finetuning.adversarial_gen import WeaknessTarget
        defaults = dict(
            model="llama3:8b",
            category="coding",
            subcategory=None,
            win_rate=0.4,
            sample_count=50,
            gap_to_target=0.2,
            priority=0.8,
        )
        defaults.update(kw)
        return WeaknessTarget(**defaults)

    def test_creation(self):
        t = self._make()
        assert t.model == "llama3:8b"
        assert t.win_rate == 0.4

    def test_optional_subcategory_none(self):
        t = self._make(subcategory=None)
        assert t.subcategory is None

    def test_optional_subcategory_set(self):
        t = self._make(subcategory="recursion")
        assert t.subcategory == "recursion"

    def test_priority_stored(self):
        t = self._make(priority=0.95)
        assert t.priority == 0.95


class TestAdversarialTask:
    def _make(self, **kw):
        from ollama_arena.finetuning.adversarial_gen import AdversarialTask, DifficultyLevel
        defaults = dict(
            task_id="task_001",
            instruction="Write a sorting algorithm",
            category="coding",
            difficulty=DifficultyLevel.HARD,
            target_model="llama3:8b",
        )
        defaults.update(kw)
        return AdversarialTask(**defaults)

    def test_creation(self):
        t = self._make()
        assert t.task_id == "task_001"
        assert t.instruction == "Write a sorting algorithm"

    def test_difficulty_is_enum(self):
        from ollama_arena.finetuning.adversarial_gen import DifficultyLevel
        t = self._make()
        assert isinstance(t.difficulty, DifficultyLevel)

    def test_default_metadata_empty(self):
        t = self._make()
        assert t.metadata == {}

    def test_custom_metadata(self):
        t = self._make(metadata={"tags": ["recursion"]})
        assert t.metadata["tags"] == ["recursion"]


# ──────────────────────────────────────────────────────────────────────────────
# dpo_pipeline — DatasetVersion, DPOPair, format_dpo_dataset, validate_dpo_dataset
# ──────────────────────────────────────────────────────────────────────────────

def _make_pair(**kw):
    from ollama_arena.finetuning.dpo_pipeline import DPOPair
    defaults = dict(
        prompt="Write hello world in Python",
        chosen="print('Hello, World!')",
        rejected="puts 'Hello, World!'",
        chosen_model="llama3:8b",
        rejected_model="phi3:3b",
        category="coding",
        task_id="t1",
        elo_gap=25.0,
        match_id=1,
    )
    defaults.update(kw)
    return DPOPair(**defaults)


class TestDatasetVersion:
    def test_creation(self):
        from ollama_arena.finetuning.dpo_pipeline import DatasetVersion
        dv = DatasetVersion(
            version_id="v1",
            created_at="2026-01-01",
            base_model="llama3:8b",
            target_model="phi3:3b",
            category="coding",
            num_pairs=10,
            min_elo_gap=5.0,
            avg_elo_gap=20.0,
            file_path="/tmp/dataset.jsonl",
            checksum="abc123",
        )
        assert dv.version_id == "v1"
        assert dv.num_pairs == 10

    def test_stored_fields(self):
        from ollama_arena.finetuning.dpo_pipeline import DatasetVersion
        dv = DatasetVersion(
            version_id="v2", created_at="2026-01-02", base_model="a",
            target_model="b", category="math", num_pairs=5,
            min_elo_gap=2.0, avg_elo_gap=10.0, file_path="x.jsonl", checksum="xyz",
        )
        assert dv.category == "math"
        assert dv.checksum == "xyz"


class TestDPOPair:
    def test_basic_fields(self):
        p = _make_pair()
        assert p.prompt == "Write hello world in Python"
        assert p.chosen_model == "llama3:8b"
        assert p.elo_gap == 25.0

    def test_default_metadata_empty(self):
        p = _make_pair()
        assert p.metadata == {}

    def test_custom_metadata(self):
        p = _make_pair(metadata={"source": "arena"})
        assert p.metadata["source"] == "arena"


class TestFormatDPODataset:
    def _pairs(self):
        return [
            _make_pair(prompt="Q1", chosen="C1", rejected="R1"),
            _make_pair(prompt="Q2", chosen="C2", rejected="R2"),
        ]

    def test_trl_format_has_prompt(self):
        from ollama_arena.finetuning.dpo_pipeline import format_dpo_dataset
        result = format_dpo_dataset(self._pairs(), "trl")
        assert result[0]["prompt"] == "Q1"
        assert result[0]["chosen"] == "C1"
        assert result[0]["rejected"] == "R1"

    def test_trl_format_has_category(self):
        from ollama_arena.finetuning.dpo_pipeline import format_dpo_dataset
        result = format_dpo_dataset(self._pairs(), "trl")
        assert "category" in result[0]

    def test_openai_format_messages(self):
        from ollama_arena.finetuning.dpo_pipeline import format_dpo_dataset
        result = format_dpo_dataset(self._pairs(), "openai")
        assert result[0]["messages"][0]["role"] == "user"
        assert result[0]["messages"][1]["role"] == "assistant"

    def test_openai_format_rejected(self):
        from ollama_arena.finetuning.dpo_pipeline import format_dpo_dataset
        result = format_dpo_dataset(self._pairs(), "openai")
        assert "rejected" in result[0]

    def test_unknown_format_raises(self):
        from ollama_arena.finetuning.dpo_pipeline import format_dpo_dataset
        with pytest.raises(ValueError, match="Unknown format_type"):
            format_dpo_dataset(self._pairs(), "unsupported")

    def test_empty_list_returns_empty(self):
        from ollama_arena.finetuning.dpo_pipeline import format_dpo_dataset
        assert format_dpo_dataset([], "trl") == []

    def test_count_matches_input(self):
        from ollama_arena.finetuning.dpo_pipeline import format_dpo_dataset
        result = format_dpo_dataset(self._pairs(), "trl")
        assert len(result) == 2


class TestValidateDPODataset:
    def test_valid_dataset_no_issues(self):
        from ollama_arena.finetuning.dpo_pipeline import validate_dpo_dataset
        pairs = [_make_pair() for _ in range(5)]
        result = validate_dpo_dataset(pairs)
        assert result["valid"] is True
        assert result["issues"] == []

    def test_empty_prompt_detected(self):
        from ollama_arena.finetuning.dpo_pipeline import validate_dpo_dataset
        pairs = [_make_pair(prompt="  ")]
        result = validate_dpo_dataset(pairs)
        assert result["valid"] is False
        assert len(result["issues"]) > 0

    def test_empty_chosen_detected(self):
        from ollama_arena.finetuning.dpo_pipeline import validate_dpo_dataset
        pairs = [_make_pair(chosen="")]
        result = validate_dpo_dataset(pairs)
        assert result["valid"] is False

    def test_empty_rejected_detected(self):
        from ollama_arena.finetuning.dpo_pipeline import validate_dpo_dataset
        pairs = [_make_pair(rejected="")]
        result = validate_dpo_dataset(pairs)
        assert result["valid"] is False

    def test_identical_chosen_rejected_detected(self):
        from ollama_arena.finetuning.dpo_pipeline import validate_dpo_dataset
        pairs = [_make_pair(chosen="same text here ok", rejected="same text here ok")]
        result = validate_dpo_dataset(pairs)
        assert result["valid"] is False

    def test_empty_dataset_returns_stats(self):
        from ollama_arena.finetuning.dpo_pipeline import validate_dpo_dataset
        result = validate_dpo_dataset([])
        assert "num_pairs" in result
        assert result["num_pairs"] == 0

    def test_stats_contain_elo_gap_info(self):
        from ollama_arena.finetuning.dpo_pipeline import validate_dpo_dataset
        pairs = [_make_pair(elo_gap=30.0), _make_pair(elo_gap=10.0)]
        result = validate_dpo_dataset(pairs)
        assert "stats" in result
        assert "elo_gap" in result["stats"]


# ──────────────────────────────────────────────────────────────────────────────
# orchestrator — JobStatus, GPUType, GPUResource, FinetuningJob
# ──────────────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────────────
# adversarial_gen — calibrate_difficulty pure paths
# ──────────────────────────────────────────────────────────────────────────────

class TestCalibrateDifficulty:
    def test_empty_tasks_returns_not_calibrated(self):
        from ollama_arena.finetuning.adversarial_gen import calibrate_difficulty
        result = calibrate_difficulty([])
        assert result["calibrated"] is False

    def test_empty_tasks_has_reason(self):
        from ollama_arena.finetuning.adversarial_gen import calibrate_difficulty
        result = calibrate_difficulty([])
        assert "reason" in result


# ──────────────────────────────────────────────────────────────────────────────
# orchestrator — JobStatus, GPUType, GPUResource, FinetuningJob
# ──────────────────────────────────────────────────────────────────────────────

class TestJobStatus:
    def test_all_values(self):
        from ollama_arena.finetuning.orchestrator import JobStatus
        values = {s.value for s in JobStatus}
        assert {"pending", "queued", "running", "completed", "failed", "cancelled"} == values

    def test_from_string(self):
        from ollama_arena.finetuning.orchestrator import JobStatus
        assert JobStatus("running") == JobStatus.RUNNING


class TestGPUType:
    def test_cuda_value(self):
        from ollama_arena.finetuning.orchestrator import GPUType
        assert GPUType.CUDA.value == "cuda"

    def test_mps_value(self):
        from ollama_arena.finetuning.orchestrator import GPUType
        assert GPUType.MPS.value == "mps"

    def test_cpu_value(self):
        from ollama_arena.finetuning.orchestrator import GPUType
        assert GPUType.CPU.value == "cpu"


class TestGPUResource:
    def test_creation(self):
        from ollama_arena.finetuning.orchestrator import GPUResource, GPUType
        gpu = GPUResource(gpu_id=0, gpu_type=GPUType.CUDA, total_memory_gb=24.0, available_memory_gb=20.0)
        assert gpu.gpu_id == 0
        assert gpu.in_use is False

    def test_default_not_in_use(self):
        from ollama_arena.finetuning.orchestrator import GPUResource, GPUType
        gpu = GPUResource(gpu_id=1, gpu_type=GPUType.CPU, total_memory_gb=0, available_memory_gb=0)
        assert gpu.in_use is False
        assert gpu.current_job_id is None


class TestFinetuningJob:
    def _make(self):
        from ollama_arena.finetuning.orchestrator import FinetuningJob, JobStatus
        return FinetuningJob(
            job_id="job_001",
            model="llama3:8b",
            category="coding",
            status=JobStatus.PENDING,
            priority=5,
            estimated_gpu_memory_gb=8.0,
            estimated_duration_minutes=30.0,
            created_at="2026-01-01",
        )

    def test_creation(self):
        job = self._make()
        assert job.job_id == "job_001"
        assert job.model == "llama3:8b"

    def test_default_optional_fields_none(self):
        job = self._make()
        assert job.started_at is None
        assert job.completed_at is None
        assert job.gpu_id is None
        assert job.error_message is None

    def test_default_metadata_empty(self):
        job = self._make()
        assert job.metadata == {}

    def test_status_is_enum(self):
        from ollama_arena.finetuning.orchestrator import JobStatus
        job = self._make()
        assert isinstance(job.status, JobStatus)
