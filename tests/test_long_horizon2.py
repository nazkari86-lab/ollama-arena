"""Additional tests for tasks/long_horizon — LongHorizonTaskManager."""
from __future__ import annotations

import json
import time
import pytest


# ──────────────────────────────────────────────────────────────────────────────
# LongHorizonTask dataclass
# ──────────────────────────────────────────────────────────────────────────────

class TestLongHorizonTask:
    def test_defaults(self):
        from ollama_arena.tasks.long_horizon import LongHorizonTask, TaskStatus
        t = LongHorizonTask(id="t1", instruction="do stuff", estimated_duration_hours=2.0)
        assert t.status == TaskStatus.NOT_STARTED
        assert t.current_progress == 0.0
        assert t.checkpoints == []
        assert t.started_at is None
        assert t.completed_at is None

    def test_created_at_is_set(self):
        from ollama_arena.tasks.long_horizon import LongHorizonTask
        before = time.time()
        t = LongHorizonTask(id="t1", instruction="x", estimated_duration_hours=1.0)
        assert t.created_at >= before


class TestTaskProgress:
    def test_defaults(self):
        from ollama_arena.tasks.long_horizon import TaskProgress
        tp = TaskProgress(
            task_id="t1", current_step=5, total_steps=10,
            step_description="doing", progress_percentage=50.0,
            time_elapsed_s=30.0, estimated_remaining_s=30.0,
        )
        assert tp.artifacts == []
        assert tp.progress_percentage == 50.0


class TestTaskEvaluationResult:
    def test_fields(self):
        from ollama_arena.tasks.long_horizon import TaskEvaluationResult
        r = TaskEvaluationResult(
            task_id="t1", overall_score=0.8, completion_percentage=80.0,
            quality_metrics={}, step_scores={}, intermediate_evaluations=[],
            final_assessment="ok", duration_s=100.0,
        )
        assert r.overall_score == 0.8


# ──────────────────────────────────────────────────────────────────────────────
# LONG_HORIZON_TASKS constant
# ──────────────────────────────────────────────────────────────────────────────

class TestLongHorizonTasksList:
    def test_has_five_tasks(self):
        from ollama_arena.tasks.long_horizon import LONG_HORIZON_TASKS
        assert len(LONG_HORIZON_TASKS) == 5

    def test_all_hard(self):
        from ollama_arena.tasks.long_horizon import LONG_HORIZON_TASKS
        for t in LONG_HORIZON_TASKS:
            assert t["difficulty"] == "hard"

    def test_all_have_checkpoints(self):
        from ollama_arena.tasks.long_horizon import LONG_HORIZON_TASKS
        for t in LONG_HORIZON_TASKS:
            assert len(t["checkpoints"]) > 0

    def test_category_is_long_horizon(self):
        from ollama_arena.tasks.long_horizon import LONG_HORIZON_TASKS
        for t in LONG_HORIZON_TASKS:
            assert t["category"] == "long_horizon"


# ──────────────────────────────────────────────────────────────────────────────
# LongHorizonTaskManager
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def manager(tmp_path):
    from ollama_arena.tasks.long_horizon import LongHorizonTaskManager
    return LongHorizonTaskManager(checkpoint_dir=tmp_path / "checkpoints")


@pytest.fixture
def task_def():
    return {
        "id": "test_001",
        "instruction": "Do something",
        "estimated_hours": 1.5,
        "difficulty": "hard",
        "role": "developer",
        "checkpoints": ["step_a", "step_b"],
    }


class TestLongHorizonTaskManagerCreate:
    def test_create_task_returns_task(self, manager, task_def):
        from ollama_arena.tasks.long_horizon import LongHorizonTask
        task = manager.create_task(task_def)
        assert isinstance(task, LongHorizonTask)
        assert task.id == "test_001"
        assert task.estimated_duration_hours == 1.5

    def test_task_stored_in_manager(self, manager, task_def):
        task = manager.create_task(task_def)
        assert "test_001" in manager.tasks

    def test_metadata_populated(self, manager, task_def):
        task = manager.create_task(task_def)
        assert task.metadata["difficulty"] == "hard"
        assert task.metadata["role"] == "developer"

    def test_default_estimated_hours(self, manager):
        task = manager.create_task({"id": "x", "instruction": "y"})
        assert task.estimated_duration_hours == 2.0


class TestLongHorizonTaskManagerStart:
    def test_start_unknown_task_returns_false(self, manager):
        assert manager.start_task("nonexistent") is False

    def test_start_sets_in_progress(self, manager, task_def):
        from ollama_arena.tasks.long_horizon import TaskStatus
        manager.create_task(task_def)
        result = manager.start_task("test_001")
        assert result is True
        assert manager.tasks["test_001"].status == TaskStatus.IN_PROGRESS

    def test_start_sets_started_at(self, manager, task_def):
        manager.create_task(task_def)
        manager.start_task("test_001")
        assert manager.tasks["test_001"].started_at is not None

    def test_start_completed_task_returns_false(self, manager, task_def):
        from ollama_arena.tasks.long_horizon import TaskStatus
        manager.create_task(task_def)
        manager.tasks["test_001"].status = TaskStatus.COMPLETED
        assert manager.start_task("test_001") is False

    def test_restart_sets_resumed(self, manager, task_def):
        from ollama_arena.tasks.long_horizon import TaskStatus
        manager.create_task(task_def)
        task = manager.tasks["test_001"]
        task.started_at = time.time() - 10  # already started before
        manager.start_task("test_001")
        assert task.status == TaskStatus.RESUMED


class TestLongHorizonTaskManagerPause:
    def test_pause_unknown_returns_false(self, manager):
        assert manager.pause_task("nonexistent") is False

    def test_pause_sets_paused(self, manager, task_def):
        from ollama_arena.tasks.long_horizon import TaskStatus
        manager.create_task(task_def)
        manager.start_task("test_001")
        result = manager.pause_task("test_001")
        assert result is True
        assert manager.tasks["test_001"].status == TaskStatus.PAUSED

    def test_pause_saves_checkpoint_file(self, manager, task_def, tmp_path):
        manager.create_task(task_def)
        manager.start_task("test_001")
        manager.pause_task("test_001")
        checkpoint_files = list((tmp_path / "checkpoints").glob("*.json"))
        assert len(checkpoint_files) >= 1


class TestLongHorizonTaskManagerResume:
    def test_resume_unknown_returns_false(self, manager):
        assert manager.resume_task("nonexistent") is False

    def test_resume_no_checkpoints(self, manager, task_def):
        from ollama_arena.tasks.long_horizon import TaskStatus
        manager.create_task(task_def)
        result = manager.resume_task("test_001")
        assert result is True
        assert manager.tasks["test_001"].status == TaskStatus.IN_PROGRESS

    def test_resume_from_latest_checkpoint(self, manager, task_def):
        from ollama_arena.tasks.long_horizon import TaskStatus
        manager.create_task(task_def)
        manager.start_task("test_001")
        manager.pause_task("test_001")
        result = manager.resume_task("test_001")
        assert result is True
        assert manager.tasks["test_001"].status == TaskStatus.RESUMED

    def test_resume_from_specific_checkpoint(self, manager, task_def):
        from ollama_arena.tasks.long_horizon import TaskStatus
        manager.create_task(task_def)
        manager.start_task("test_001")
        manager.pause_task("test_001")
        # Get the checkpoint id
        checkpoint = manager.tasks["test_001"].checkpoints[0]
        result = manager.resume_task("test_001", checkpoint_id=checkpoint.checkpoint_id)
        assert result is True

    def test_resume_with_bad_checkpoint_id_falls_through(self, manager, task_def):
        from ollama_arena.tasks.long_horizon import TaskStatus
        manager.create_task(task_def)
        manager.start_task("test_001")
        result = manager.resume_task("test_001", checkpoint_id="no_such_checkpoint")
        assert result is True
        assert manager.tasks["test_001"].status == TaskStatus.IN_PROGRESS


class TestLongHorizonTaskManagerComplete:
    def test_complete_unknown_returns_false(self, manager):
        assert manager.complete_task("nonexistent", {}) is False

    def test_complete_sets_status(self, manager, task_def):
        from ollama_arena.tasks.long_horizon import TaskStatus
        manager.create_task(task_def)
        manager.start_task("test_001")
        result = manager.complete_task("test_001", {"final": "done"})
        assert result is True
        task = manager.tasks["test_001"]
        assert task.status == TaskStatus.COMPLETED
        assert task.current_progress == 1.0
        assert task.intermediate_results["final"] == "done"

    def test_complete_creates_checkpoint(self, manager, task_def, tmp_path):
        manager.create_task(task_def)
        manager.start_task("test_001")
        manager.complete_task("test_001", {})
        files = list((tmp_path / "checkpoints").glob("*.json"))
        assert len(files) >= 1


class TestLongHorizonTaskManagerFail:
    def test_fail_unknown_returns_false(self, manager):
        assert manager.fail_task("nonexistent", "err") is False

    def test_fail_sets_failed_status(self, manager, task_def):
        from ollama_arena.tasks.long_horizon import TaskStatus
        manager.create_task(task_def)
        manager.fail_task("test_001", "timeout")
        task = manager.tasks["test_001"]
        assert task.status == TaskStatus.FAILED
        assert "timeout" in task.metadata["error"]


class TestLongHorizonTaskManagerProgress:
    def test_update_progress_unknown_returns_none(self, manager):
        result = manager.update_progress("nonexistent", 0.5, "doing")
        assert result is None

    def test_update_progress_returns_task_progress(self, manager, task_def):
        from ollama_arena.tasks.long_horizon import TaskProgress
        manager.create_task(task_def)
        manager.start_task("test_001")
        result = manager.update_progress("test_001", 0.5, "halfway", artifacts=["file.txt"])
        assert isinstance(result, TaskProgress)
        assert result.progress_percentage == pytest.approx(50.0)
        assert "file.txt" in result.artifacts

    def test_progress_clamped_to_1(self, manager, task_def):
        manager.create_task(task_def)
        manager.update_progress("test_001", 1.5, "overflow")
        assert manager.tasks["test_001"].current_progress == 1.0

    def test_progress_clamped_to_0(self, manager, task_def):
        manager.create_task(task_def)
        manager.update_progress("test_001", -0.5, "underflow")
        assert manager.tasks["test_001"].current_progress == 0.0

    def test_estimated_remaining_when_zero_progress(self, manager, task_def):
        manager.create_task(task_def)
        result = manager.update_progress("test_001", 0.0, "start")
        assert result.estimated_remaining_s == 0.0


class TestLongHorizonTaskManagerSaveResult:
    def test_save_intermediate_unknown_returns_false(self, manager):
        assert manager.save_intermediate_result("nonexistent", "key", "val") is False

    def test_save_intermediate_stores_value(self, manager, task_def):
        manager.create_task(task_def)
        result = manager.save_intermediate_result("test_001", "output", [1, 2, 3])
        assert result is True
        assert manager.tasks["test_001"].intermediate_results["output"] == [1, 2, 3]


class TestLongHorizonTaskManagerEvaluate:
    def test_evaluate_unknown_returns_none(self, manager):
        from ollama_arena.tasks.long_horizon import TaskStatus
        result = manager.evaluate_task("nonexistent", lambda t: None)
        assert result is None

    def test_evaluate_non_completed_returns_none(self, manager, task_def):
        from ollama_arena.tasks.long_horizon import TaskStatus
        manager.create_task(task_def)
        result = manager.evaluate_task("test_001", lambda t: "something")
        assert result is None

    def test_evaluate_calls_evaluator(self, manager, task_def):
        from ollama_arena.tasks.long_horizon import TaskStatus
        manager.create_task(task_def)
        manager.tasks["test_001"].status = TaskStatus.COMPLETED
        called_with = []
        def mock_eval(task):
            called_with.append(task)
            return "evaluated"
        result = manager.evaluate_task("test_001", mock_eval)
        assert result == "evaluated"
        assert len(called_with) == 1


class TestLongHorizonTaskManagerListGet:
    def test_list_all(self, manager, task_def):
        manager.create_task(task_def)
        tasks = manager.list_tasks()
        assert len(tasks) == 1

    def test_list_filter_by_status(self, manager, task_def):
        from ollama_arena.tasks.long_horizon import TaskStatus
        manager.create_task(task_def)
        manager.start_task("test_001")
        in_progress = manager.list_tasks(status=TaskStatus.IN_PROGRESS)
        not_started = manager.list_tasks(status=TaskStatus.NOT_STARTED)
        assert len(in_progress) == 1
        assert len(not_started) == 0

    def test_get_task_returns_task(self, manager, task_def):
        manager.create_task(task_def)
        assert manager.get_task("test_001") is not None

    def test_get_task_unknown_returns_none(self, manager):
        assert manager.get_task("nonexistent") is None


class TestLongHorizonTaskManagerCheckpoints:
    def test_save_load_checkpoint(self, manager, task_def):
        from ollama_arena.tasks.long_horizon import CheckpointState
        manager.create_task(task_def)
        manager.start_task("test_001")
        manager.pause_task("test_001")
        checkpoint = manager.tasks["test_001"].checkpoints[0]
        assert checkpoint.state == CheckpointState.SAVED
        loaded = manager._load_checkpoint(checkpoint.checkpoint_id)
        assert loaded is not None
        assert loaded.task_id == "test_001"

    def test_load_missing_checkpoint_returns_none(self, manager):
        result = manager._load_checkpoint("no_such_checkpoint_id")
        assert result is None

    def test_restore_checkpoint_updates_task(self, manager, task_def):
        manager.create_task(task_def)
        task = manager.tasks["test_001"]
        task.current_progress = 0.5
        manager.pause_task("test_001")
        checkpoint = task.checkpoints[0]
        task.current_progress = 0.0  # reset
        manager._restore_checkpoint(task, checkpoint)
        assert task.current_progress == pytest.approx(0.5)

    def test_restore_checkpoint_drops_results_added_after_checkpoint(self, manager, task_def):
        """Regression: rolling back to an earlier checkpoint must not leave behind
        intermediate results saved after that checkpoint was taken. Previously
        _restore_checkpoint() merged (dict.update) instead of replacing
        intermediate_results, so a later attempt's data survived a rollback."""
        manager.create_task(task_def)
        manager.start_task("test_001")
        manager.save_intermediate_result("test_001", "step1_result", "A")
        manager.pause_task("test_001")
        early_checkpoint = manager.tasks["test_001"].checkpoints[0]

        manager.start_task("test_001")
        manager.save_intermediate_result("test_001", "step2_result", "B")

        manager.resume_task("test_001", checkpoint_id=early_checkpoint.checkpoint_id)

        results = manager.tasks["test_001"].intermediate_results
        assert "step1_result" in results
        assert "step2_result" not in results

    def test_restore_checkpoint_resets_progress_backward(self, manager, task_def):
        manager.create_task(task_def)
        manager.start_task("test_001")
        manager.update_progress("test_001", 0.3, "early")
        manager.pause_task("test_001")
        early_checkpoint = manager.tasks["test_001"].checkpoints[0]

        manager.start_task("test_001")
        manager.update_progress("test_001", 0.9, "later")

        manager.resume_task("test_001", checkpoint_id=early_checkpoint.checkpoint_id)
        assert manager.tasks["test_001"].current_progress == pytest.approx(0.3)

    def test_rapid_checkpoints_get_unique_ids(self, manager, task_def):
        """Regression: checkpoint_id was f"{task_id}_{int(time.time())}" — two
        checkpoints created within the same wall-clock second collided, and the
        second _save_checkpoint() silently overwrote the first checkpoint's file
        on disk, making the earlier checkpoint unrecoverable by its own id."""
        manager.create_task(task_def)
        manager.start_task("test_001")
        manager.update_progress("test_001", 0.2, "first")
        manager.pause_task("test_001")
        cp1 = manager.tasks["test_001"].checkpoints[-1]

        manager.start_task("test_001")
        manager.update_progress("test_001", 0.8, "second")
        manager.pause_task("test_001")
        cp2 = manager.tasks["test_001"].checkpoints[-1]

        assert cp1.checkpoint_id != cp2.checkpoint_id

        loaded1 = manager._load_checkpoint(cp1.checkpoint_id)
        loaded2 = manager._load_checkpoint(cp2.checkpoint_id)
        assert loaded1.progress == pytest.approx(0.2)
        assert loaded2.progress == pytest.approx(0.8)


# ──────────────────────────────────────────────────────────────────────────────
# default_task_evaluator
# ──────────────────────────────────────────────────────────────────────────────

class TestDefaultTaskEvaluator:
    def _make_task(self, n_checkpoints=3, progress=0.8):
        from ollama_arena.tasks.long_horizon import (
            LongHorizonTask, TaskStatus, TaskCheckpoint, CheckpointState
        )
        task = LongHorizonTask(id="t1", instruction="x", estimated_duration_hours=2.0)
        task.status = TaskStatus.COMPLETED
        task.current_progress = progress
        task.started_at = time.time() - 100
        task.completed_at = time.time()
        for i in range(n_checkpoints):
            task.checkpoints.append(
                TaskCheckpoint(
                    checkpoint_id=f"cp_{i}", task_id="t1",
                    timestamp=time.time(), state=CheckpointState.SAVED,
                    progress=i / 5, data={}, intermediate_results={}, metadata={},
                )
            )
        return task

    def test_returns_evaluation_result(self):
        from ollama_arena.tasks.long_horizon import (
            TaskEvaluationResult, default_task_evaluator
        )
        task = self._make_task()
        result = default_task_evaluator(task)
        assert isinstance(result, TaskEvaluationResult)

    def test_score_in_range(self):
        from ollama_arena.tasks.long_horizon import default_task_evaluator
        task = self._make_task()
        result = default_task_evaluator(task)
        assert 0.0 <= result.overall_score <= 1.0

    def test_completion_percentage(self):
        from ollama_arena.tasks.long_horizon import default_task_evaluator
        task = self._make_task(progress=0.5)
        result = default_task_evaluator(task)
        assert result.completion_percentage == pytest.approx(50.0)

    def test_step_scores_match_checkpoints(self):
        from ollama_arena.tasks.long_horizon import default_task_evaluator
        task = self._make_task(n_checkpoints=3)
        result = default_task_evaluator(task)
        assert len(result.step_scores) == 3

    def test_no_duration_when_no_started_at(self):
        from ollama_arena.tasks.long_horizon import (
            LongHorizonTask, default_task_evaluator
        )
        task = LongHorizonTask(id="t1", instruction="x", estimated_duration_hours=1.0)
        result = default_task_evaluator(task)
        assert result.duration_s == 0
