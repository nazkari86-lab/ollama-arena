"""Long-Horizon Task Category.

Extends task system to support multi-hour tasks with checkpoint/resume
functionality, progress tracking, and intermediate result evaluation.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

log = logging.getLogger("arena.tasks.long_horizon")


class TaskStatus(str, Enum):
    """Status of long-horizon task execution."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    RESUMED = "resumed"


class CheckpointState(str, Enum):
    """State of a checkpoint."""
    PENDING = "pending"
    SAVED = "saved"
    RESTORED = "restored"
    FAILED = "failed"


@dataclass
class TaskCheckpoint:
    """Checkpoint for resuming long-horizon tasks."""
    checkpoint_id: str
    task_id: str
    timestamp: float
    state: CheckpointState
    progress: float  # 0.0 to 1.0
    data: dict[str, Any]
    intermediate_results: dict[str, Any]
    metadata: dict[str, Any]


@dataclass
class LongHorizonTask:
    """A long-horizon task that spans multiple execution sessions."""
    id: str
    instruction: str
    estimated_duration_hours: float
    status: TaskStatus = TaskStatus.NOT_STARTED
    checkpoints: list[TaskCheckpoint] = field(default_factory=list)
    current_progress: float = 0.0
    intermediate_results: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


@dataclass
class TaskProgress:
    """Progress tracking for long-horizon tasks."""
    task_id: str
    current_step: int
    total_steps: int
    step_description: str
    progress_percentage: float
    time_elapsed_s: float
    estimated_remaining_s: float
    artifacts: list[str] = field(default_factory=list)


@dataclass
class TaskEvaluationResult:
    """Result of evaluating a long-horizon task."""
    task_id: str
    overall_score: float  # 0.0 to 1.0
    completion_percentage: float
    quality_metrics: dict[str, float]
    step_scores: dict[str, float]
    intermediate_evaluations: list[dict[str, Any]]
    final_assessment: str
    duration_s: float


# Long-horizon task definitions
LONG_HORIZON_TASKS = [
    {
        "id": "lh_001",
        "difficulty": "hard",
        "category": "long_horizon",
        "role": "developer",
        "estimated_hours": 2.0,
        "instruction": (
            "You are working on a large open-source Python project. "
            "Your task is to:\n"
            "1. Explore the codebase to understand the architecture\n"
            "2. Find and fix a bug in the authentication module\n"
            "3. Write comprehensive unit tests for the fix\n"
            "4. Create a pull request with proper documentation\n"
            "5. Respond to code review feedback\n\n"
            "This task requires multiple steps and may take several hours. "
            "Use checkpoints to save your progress."
        ),
        "checkpoints": [
            "codebase_exploration",
            "bug_identification",
            "fix_implementation",
            "test_writing",
            "pr_creation",
        ],
    },
    {
        "id": "lh_002",
        "difficulty": "hard",
        "category": "long_horizon",
        "role": "architect",
        "estimated_hours": 3.0,
        "instruction": (
            "Design and implement a microservice architecture for a web application:\n"
            "1. Analyze requirements and design the system architecture\n"
            "2. Create service definitions and API contracts\n"
            "3. Implement core services with proper error handling\n"
            "4. Add monitoring and logging infrastructure\n"
            "5. Write deployment configuration (Docker/Kubernetes)\n"
            "6. Create integration tests\n\n"
            "This is a complex, multi-hour task. Save progress frequently."
        ),
        "checkpoints": [
            "architecture_design",
            "api_contracts",
            "service_implementation",
            "monitoring_setup",
            "deployment_config",
            "integration_tests",
        ],
    },
    {
        "id": "lh_003",
        "difficulty": "hard",
        "category": "long_horizon",
        "role": "researcher",
        "estimated_hours": 4.0,
        "instruction": (
            "Conduct a comprehensive research project on a technical topic:\n"
            "1. Define research questions and methodology\n"
            "2. Gather and analyze data from multiple sources\n"
            "3. Synthesize findings into a coherent report\n"
            "4. Create visualizations and supporting materials\n"
            "5. Write a final paper with citations and references\n\n"
            "This research task may span multiple sessions."
        ),
        "checkpoints": [
            "research_design",
            "data_collection",
            "analysis_phase",
            "synthesis",
            "documentation",
        ],
    },
    {
        "id": "lh_004",
        "difficulty": "hard",
        "category": "long_horizon",
        "role": "developer",
        "estimated_hours": 2.5,
        "instruction": (
            "Refactor a large legacy codebase:\n"
            "1. Analyze the existing code structure and dependencies\n"
            "2. Identify technical debt and anti-patterns\n"
            "3. Plan the refactoring approach with minimal risk\n"
            "4. Incrementally refactor modules while maintaining functionality\n"
            "5. Add tests to prevent regression\n"
            "6. Update documentation\n\n"
            "This is a high-risk task requiring careful progress tracking."
        ),
        "checkpoints": [
            "code_analysis",
            "debt_identification",
            "refactoring_plan",
            "incremental_refactor",
            "test_coverage",
            "documentation_update",
        ],
    },
    {
        "id": "lh_005",
        "difficulty": "hard",
        "category": "long_horizon",
        "role": "developer",
        "estimated_hours": 1.5,
        "instruction": (
            "Implement a complex algorithm from scratch:\n"
            "1. Research the algorithm and understand its theoretical basis\n"
            "2. Design the implementation approach\n"
            "3. Write the initial implementation\n"
            "4. Optimize for performance\n"
            "5. Add comprehensive test cases\n"
            "6. Document the implementation and edge cases\n\n"
            "This task requires deep technical understanding."
        ),
        "checkpoints": [
            "algorithm_research",
            "design_phase",
            "initial_implementation",
            "optimization",
            "testing",
            "documentation",
        ],
    },
]


class LongHorizonTaskManager:
    """Manager for long-horizon tasks with checkpoint/resume support."""

    def __init__(self, checkpoint_dir: Optional[Path] = None):
        self.checkpoint_dir = checkpoint_dir or Path(".long_horizon_checkpoints")
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.tasks: dict[str, LongHorizonTask] = {}

    def create_task(
        self,
        task_def: dict[str, Any],
    ) -> LongHorizonTask:
        """Create a new long-horizon task from definition."""
        task = LongHorizonTask(
            id=task_def["id"],
            instruction=task_def["instruction"],
            estimated_duration_hours=task_def.get("estimated_hours", 2.0),
            metadata={
                "difficulty": task_def.get("difficulty", "hard"),
                "role": task_def.get("role", "developer"),
                "checkpoints": task_def.get("checkpoints", []),
            },
        )
        self.tasks[task.id] = task
        return task

    def start_task(self, task_id: str) -> bool:
        """Start execution of a task."""
        if task_id not in self.tasks:
            log.warning(f"Task {task_id} not found")
            return False

        task = self.tasks[task_id]
        if task.status == TaskStatus.COMPLETED:
            log.warning(f"Task {task_id} already completed")
            return False

        task.status = TaskStatus.IN_PROGRESS
        if task.started_at is None:
            task.started_at = time.time()
        else:
            task.status = TaskStatus.RESUMED

        log.info(f"Started task {task_id}")
        return True

    def pause_task(self, task_id: str) -> bool:
        """Pause a task and create checkpoint."""
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]
        task.status = TaskStatus.PAUSED

        # Create automatic checkpoint
        checkpoint = self._create_checkpoint(task)
        task.checkpoints.append(checkpoint)
        self._save_checkpoint(checkpoint)

        log.info(f"Paused task {task_id} with checkpoint {checkpoint.checkpoint_id}")
        return True

    def resume_task(self, task_id: str, checkpoint_id: Optional[str] = None) -> bool:
        """Resume a task from checkpoint."""
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]

        if checkpoint_id:
            # Restore from specific checkpoint
            checkpoint = self._load_checkpoint(checkpoint_id)
            if checkpoint and checkpoint.task_id == task_id:
                self._restore_checkpoint(task, checkpoint)
                task.status = TaskStatus.RESUMED
                log.info(f"Resumed task {task_id} from checkpoint {checkpoint_id}")
                return True
        else:
            # Resume from latest checkpoint
            if task.checkpoints:
                latest = task.checkpoints[-1]
                self._restore_checkpoint(task, latest)
                task.status = TaskStatus.RESUMED
                log.info(f"Resumed task {task_id} from latest checkpoint")
                return True

        # No checkpoint, just resume
        task.status = TaskStatus.IN_PROGRESS
        return True

    def complete_task(self, task_id: str, final_results: dict[str, Any]) -> bool:
        """Mark a task as completed with final results."""
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]
        task.status = TaskStatus.COMPLETED
        task.completed_at = time.time()
        task.intermediate_results.update(final_results)
        task.current_progress = 1.0

        # Create final checkpoint
        checkpoint = self._create_checkpoint(task)
        task.checkpoints.append(checkpoint)
        self._save_checkpoint(checkpoint)

        log.info(f"Completed task {task_id}")
        return True

    def fail_task(self, task_id: str, error: str) -> bool:
        """Mark a task as failed."""
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]
        task.status = TaskStatus.FAILED
        task.metadata["error"] = error

        log.info(f"Failed task {task_id}: {error}")
        return True

    def update_progress(
        self,
        task_id: str,
        progress: float,
        step_description: str,
        artifacts: Optional[list[str]] = None,
    ) -> Optional[TaskProgress]:
        """Update progress of a task."""
        if task_id not in self.tasks:
            return None

        task = self.tasks[task_id]
        task.current_progress = max(0.0, min(1.0, progress))

        elapsed = 0.0
        if task.started_at:
            elapsed = time.time() - task.started_at

        estimated_remaining = 0.0
        if task.estimated_duration_hours > 0 and progress > 0:
            total_estimated = task.estimated_duration_hours * 3600
            estimated_remaining = total_estimated * (1 - progress) / progress

        task_progress = TaskProgress(
            task_id=task_id,
            current_step=int(progress * 100),
            total_steps=100,
            step_description=step_description,
            progress_percentage=progress * 100,
            time_elapsed_s=elapsed,
            estimated_remaining_s=estimated_remaining,
            artifacts=artifacts or [],
        )

        return task_progress

    def save_intermediate_result(
        self,
        task_id: str,
        key: str,
        value: Any,
    ) -> bool:
        """Save an intermediate result for a task."""
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]
        task.intermediate_results[key] = value
        return True

    def evaluate_task(
        self,
        task_id: str,
        evaluator: Callable[[LongHorizonTask], TaskEvaluationResult],
    ) -> Optional[TaskEvaluationResult]:
        """Evaluate a completed task."""
        if task_id not in self.tasks:
            return None

        task = self.tasks[task_id]
        if task.status != TaskStatus.COMPLETED:
            log.warning(f"Cannot evaluate task {task_id}: not completed")
            return None

        return evaluator(task)

    def _create_checkpoint(self, task: LongHorizonTask) -> TaskCheckpoint:
        """Create a checkpoint for a task."""
        # Second-granularity alone collides under rapid pause/resume/complete cycles
        # within the same wall-clock second, silently overwriting an earlier
        # checkpoint's on-disk file with a later one's data. The sequence number
        # makes each checkpoint_id unique regardless of timing.
        checkpoint_id = f"{task.id}_{int(time.time())}_{len(task.checkpoints)}"
        return TaskCheckpoint(
            checkpoint_id=checkpoint_id,
            task_id=task.id,
            timestamp=time.time(),
            state=CheckpointState.PENDING,
            progress=task.current_progress,
            data={
                "status": task.status.value,
                "intermediate_results": task.intermediate_results,
                "metadata": task.metadata,
            },
            intermediate_results=dict(task.intermediate_results),
            metadata={
                "current_progress": task.current_progress,
                "estimated_remaining": task.estimated_duration_hours * (1 - task.current_progress),
            },
        )

    def _save_checkpoint(self, checkpoint: TaskCheckpoint) -> bool:
        """Save checkpoint to disk."""
        try:
            checkpoint_path = self.checkpoint_dir / f"{checkpoint.checkpoint_id}.json"
            with open(checkpoint_path, "w") as f:
                json.dump(
                    {
                        "checkpoint_id": checkpoint.checkpoint_id,
                        "task_id": checkpoint.task_id,
                        "timestamp": checkpoint.timestamp,
                        "state": checkpoint.state.value,
                        "progress": checkpoint.progress,
                        "data": checkpoint.data,
                        "intermediate_results": checkpoint.intermediate_results,
                        "metadata": checkpoint.metadata,
                    },
                    f,
                    indent=2,
                )
            checkpoint.state = CheckpointState.SAVED
            return True
        except Exception as e:
            log.error(f"Failed to save checkpoint {checkpoint.checkpoint_id}: {e}")
            checkpoint.state = CheckpointState.FAILED
            return False

    def _load_checkpoint(self, checkpoint_id: str) -> Optional[TaskCheckpoint]:
        """Load checkpoint from disk."""
        try:
            checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.json"
            if not checkpoint_path.exists():
                return None

            with open(checkpoint_path, "r") as f:
                data = json.load(f)

            return TaskCheckpoint(
                checkpoint_id=data["checkpoint_id"],
                task_id=data["task_id"],
                timestamp=data["timestamp"],
                state=CheckpointState(data["state"]),
                progress=data["progress"],
                data=data["data"],
                intermediate_results=data["intermediate_results"],
                metadata=data["metadata"],
            )
        except Exception as e:
            log.error(f"Failed to load checkpoint {checkpoint_id}: {e}")
            return None

    def _restore_checkpoint(self, task: LongHorizonTask, checkpoint: TaskCheckpoint) -> None:
        """Restore task state from checkpoint.

        Replaces (not merges) intermediate_results so that results saved after this
        checkpoint was taken (e.g. from a later attempt that is now being rolled back)
        don't survive a rollback to an earlier checkpoint. task.metadata legitimately
        mixes static config (difficulty/role/checkpoints, set once at task creation)
        with checkpoint-derived progress info, so it is still merged.
        """
        task.current_progress = checkpoint.progress
        task.intermediate_results = dict(checkpoint.intermediate_results)
        task.metadata.update(checkpoint.metadata)
        checkpoint.state = CheckpointState.RESTORED

    def list_tasks(self, status: Optional[TaskStatus] = None) -> list[LongHorizonTask]:
        """List tasks, optionally filtered by status."""
        if status:
            return [t for t in self.tasks.values() if t.status == status]
        return list(self.tasks.values())

    def get_task(self, task_id: str) -> Optional[LongHorizonTask]:
        """Get a task by ID."""
        return self.tasks.get(task_id)


def default_task_evaluator(task: LongHorizonTask) -> TaskEvaluationResult:
    """Default evaluator for long-horizon tasks."""
    # Simplified evaluation - in production would use actual assessment
    completion_score = task.current_progress

    # Quality metrics based on checkpoints and intermediate results
    checkpoint_count = len(task.checkpoints)
    quality = min(1.0, checkpoint_count / 5.0)  # Assume 5 checkpoints is ideal

    overall_score = 0.7 * completion_score + 0.3 * quality
    duration = task.completed_at - task.started_at if task.completed_at and task.started_at else 0

    return TaskEvaluationResult(
        task_id=task.id,
        overall_score=round(overall_score, 3),
        completion_percentage=round(completion_score * 100, 1),
        quality_metrics={
            "checkpoint_coverage": quality,
            "intermediate_results_count": len(task.intermediate_results),
        },
        step_scores={f"step_{i}": 1.0 for i in range(checkpoint_count)},
        intermediate_evaluations=[],
        final_assessment=(
            f"Task completed with {completion_score*100:.1f}% completion. "
            f"Quality score: {quality:.3f}"
        ),
        duration_s=duration,
    )
