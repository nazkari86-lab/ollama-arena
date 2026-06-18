"""Tests for tasks/long_horizon dataclasses and enums."""
import time

import pytest


class TestTaskStatus:
    def test_all_values(self):
        from ollama_arena.tasks.long_horizon import TaskStatus
        assert TaskStatus.NOT_STARTED == "not_started"
        assert TaskStatus.IN_PROGRESS == "in_progress"
        assert TaskStatus.PAUSED      == "paused"
        assert TaskStatus.COMPLETED   == "completed"
        assert TaskStatus.FAILED      == "failed"
        assert TaskStatus.RESUMED     == "resumed"
        assert len(TaskStatus) == 6

    def test_is_string_enum(self):
        from ollama_arena.tasks.long_horizon import TaskStatus
        assert TaskStatus.COMPLETED.value == "completed"


class TestCheckpointState:
    def test_all_values(self):
        from ollama_arena.tasks.long_horizon import CheckpointState
        assert CheckpointState.PENDING  == "pending"
        assert CheckpointState.SAVED    == "saved"
        assert CheckpointState.RESTORED == "restored"
        assert CheckpointState.FAILED   == "failed"
        assert len(CheckpointState) == 4


class TestTaskCheckpoint:
    def test_create(self):
        from ollama_arena.tasks.long_horizon import TaskCheckpoint, CheckpointState
        cp = TaskCheckpoint(
            checkpoint_id="cp-001",
            task_id="task-abc",
            timestamp=time.time(),
            state=CheckpointState.SAVED,
            progress=0.5,
            data={"step": 3},
            intermediate_results={"score": 0.8},
            metadata={"created_by": "test"},
        )
        assert cp.checkpoint_id == "cp-001"
        assert cp.progress == 0.5
        assert cp.state == CheckpointState.SAVED
        assert cp.data["step"] == 3

    def test_zero_progress(self):
        from ollama_arena.tasks.long_horizon import TaskCheckpoint, CheckpointState
        cp = TaskCheckpoint(
            checkpoint_id="cp-000",
            task_id="t1",
            timestamp=0.0,
            state=CheckpointState.PENDING,
            progress=0.0,
            data={}, intermediate_results={}, metadata={},
        )
        assert cp.progress == 0.0

    def test_full_progress(self):
        from ollama_arena.tasks.long_horizon import TaskCheckpoint, CheckpointState
        cp = TaskCheckpoint(
            checkpoint_id="cp-fin",
            task_id="t2",
            timestamp=1.0,
            state=CheckpointState.RESTORED,
            progress=1.0,
            data={}, intermediate_results={"answer": 42}, metadata={},
        )
        assert cp.progress == 1.0
        assert cp.intermediate_results["answer"] == 42


class TestLongHorizonModuleImport:
    def test_module_loads(self):
        from ollama_arena.tasks import long_horizon
        assert hasattr(long_horizon, "TaskStatus")
        assert hasattr(long_horizon, "CheckpointState")
        assert hasattr(long_horizon, "TaskCheckpoint")

    def test_task_status_terminal_states(self):
        from ollama_arena.tasks.long_horizon import TaskStatus
        terminal = {TaskStatus.COMPLETED, TaskStatus.FAILED}
        assert TaskStatus.COMPLETED in terminal
        assert TaskStatus.IN_PROGRESS not in terminal
