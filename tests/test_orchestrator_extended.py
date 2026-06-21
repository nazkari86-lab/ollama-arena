"""Extended tests for finetuning orchestrator — GPUAllocator preferred type, cancel_job, FinetuningMonitor."""
from __future__ import annotations

import pytest


def _make_job(job_id="j1", priority=5, memory=8.0):
    from ollama_arena.finetuning.orchestrator import FinetuningJob, JobStatus
    return FinetuningJob(
        job_id=job_id,
        model="llama3:8b",
        category="coding",
        status=JobStatus.PENDING,
        priority=priority,
        estimated_gpu_memory_gb=memory,
        estimated_duration_minutes=30.0,
        created_at="2026-01-01",
    )


# ──────────────────────────────────────────────────────────────────────────────
# GPUAllocator — preferred type and available memory with type filter
# ──────────────────────────────────────────────────────────────────────────────

class TestGPUAllocatorPreferredType:
    def _make_allocator_with_gpu(self, gpu_type=None, memory=32.0):
        from ollama_arena.finetuning.orchestrator import GPUAllocator, GPUResource, GPUType
        gpu_type = gpu_type or GPUType.CPU
        allocator = GPUAllocator()
        allocator.gpus = [
            GPUResource(gpu_id=0, gpu_type=gpu_type, total_memory_gb=memory, available_memory_gb=memory)
        ]
        return allocator

    def test_allocate_wrong_type_returns_none(self):
        from ollama_arena.finetuning.orchestrator import GPUAllocator, GPUType, GPUResource
        allocator = GPUAllocator()
        allocator.gpus = [
            GPUResource(gpu_id=0, gpu_type=GPUType.CPU, total_memory_gb=32, available_memory_gb=32)
        ]
        result = allocator.allocate_gpu(required_memory_gb=8.0, preferred_type=GPUType.CUDA)
        assert result is None

    def test_allocate_correct_type_returns_gpu(self):
        from ollama_arena.finetuning.orchestrator import GPUAllocator, GPUType, GPUResource
        allocator = GPUAllocator()
        allocator.gpus = [
            GPUResource(gpu_id=0, gpu_type=GPUType.MPS, total_memory_gb=32, available_memory_gb=32)
        ]
        result = allocator.allocate_gpu(required_memory_gb=8.0, preferred_type=GPUType.MPS)
        assert result is not None
        assert result.gpu_type == GPUType.MPS

    def test_get_available_memory_with_type_filter(self):
        from ollama_arena.finetuning.orchestrator import GPUAllocator, GPUType, GPUResource
        allocator = GPUAllocator()
        allocator.gpus = [
            GPUResource(gpu_id=0, gpu_type=GPUType.CPU, total_memory_gb=8.0, available_memory_gb=8.0),
            GPUResource(gpu_id=1, gpu_type=GPUType.CUDA, total_memory_gb=24.0, available_memory_gb=24.0),
        ]
        cuda_mem = allocator.get_available_memory(gpu_type=GPUType.CUDA)
        cpu_mem = allocator.get_available_memory(gpu_type=GPUType.CPU)
        assert cuda_mem == pytest.approx(24.0)
        assert cpu_mem == pytest.approx(8.0)

    def test_get_available_memory_excludes_in_use(self):
        from ollama_arena.finetuning.orchestrator import GPUAllocator, GPUType, GPUResource
        allocator = GPUAllocator()
        gpu = GPUResource(gpu_id=0, gpu_type=GPUType.CPU, total_memory_gb=32, available_memory_gb=32)
        gpu.in_use = True
        allocator.gpus = [gpu]
        mem = allocator.get_available_memory()
        assert mem == 0.0

    def test_allocate_insufficient_memory_returns_none(self):
        from ollama_arena.finetuning.orchestrator import GPUAllocator, GPUType, GPUResource
        allocator = GPUAllocator()
        allocator.gpus = [
            GPUResource(gpu_id=0, gpu_type=GPUType.CPU, total_memory_gb=4.0, available_memory_gb=4.0)
        ]
        result = allocator.allocate_gpu(required_memory_gb=8.0)
        assert result is None

    def test_get_status_with_multiple_gpus(self):
        from ollama_arena.finetuning.orchestrator import GPUAllocator, GPUType, GPUResource
        allocator = GPUAllocator()
        allocator.gpus = [
            GPUResource(gpu_id=0, gpu_type=GPUType.CPU, total_memory_gb=8, available_memory_gb=8),
            GPUResource(gpu_id=1, gpu_type=GPUType.CPU, total_memory_gb=8, available_memory_gb=8),
        ]
        status = allocator.get_status()
        assert len(status) == 2
        assert status[0]["gpu_id"] == 0
        assert status[1]["gpu_id"] == 1


# ──────────────────────────────────────────────────────────────────────────────
# JobQueue.requeue — regression test for jobs silently dropped on GPU-busy retry
# ──────────────────────────────────────────────────────────────────────────────

class TestJobQueueRequeue:
    def test_requeue_dequeued_job_succeeds(self):
        """Regression test: when the orchestrator's worker loop couldn't get a
        GPU for a dequeued job, it called JobQueue.enqueue(job) to put it back.
        But the job's id is still tracked in _jobs (dequeue only removes it
        from the internal Queue, not from _jobs), so enqueue() always rejected
        it as a duplicate and the job vanished — stuck in RUNNING forever.
        requeue() must succeed and restore it to the queue."""
        from ollama_arena.finetuning.orchestrator import JobQueue, JobStatus
        q = JobQueue()
        job = _make_job("requeue_me")
        q.enqueue(job)
        dequeued = q.dequeue(timeout=0.5)
        assert dequeued is not None
        assert dequeued.status == JobStatus.RUNNING

        result = q.requeue(dequeued)
        assert result is True
        assert dequeued.status == JobStatus.QUEUED
        assert q._queue.qsize() == 1

    def test_requeued_job_can_be_dequeued_again(self):
        from ollama_arena.finetuning.orchestrator import JobQueue, JobStatus
        q = JobQueue()
        job = _make_job("requeue_again")
        q.enqueue(job)
        dequeued = q.dequeue(timeout=0.5)
        q.requeue(dequeued)
        redequeued = q.dequeue(timeout=0.5)
        assert redequeued is not None
        assert redequeued.job_id == "requeue_again"
        assert redequeued.status == JobStatus.RUNNING


# ──────────────────────────────────────────────────────────────────────────────
# JobQueue.cancel_job
# ──────────────────────────────────────────────────────────────────────────────

class TestJobQueueCancelJob:
    def test_cancel_nonexistent_returns_false(self):
        from ollama_arena.finetuning.orchestrator import JobQueue
        q = JobQueue()
        assert q.cancel_job("nonexistent") is False

    def test_cancel_queued_job_sets_cancelled(self):
        from ollama_arena.finetuning.orchestrator import JobQueue, JobStatus
        q = JobQueue()
        job = _make_job("cancel_me")
        q.enqueue(job)
        result = q.cancel_job("cancel_me")
        assert result is True
        assert job.status == JobStatus.CANCELLED

    def test_cancel_completed_job_returns_false(self):
        from ollama_arena.finetuning.orchestrator import JobQueue, JobStatus
        q = JobQueue()
        job = _make_job("done_job")
        q.enqueue(job)
        q.update_job("done_job", status=JobStatus.COMPLETED)
        result = q.cancel_job("done_job")
        assert result is False

    def test_cancel_failed_job_returns_false(self):
        from ollama_arena.finetuning.orchestrator import JobQueue, JobStatus
        q = JobQueue()
        job = _make_job("failed_job")
        q.enqueue(job)
        q.update_job("failed_job", status=JobStatus.FAILED)
        result = q.cancel_job("failed_job")
        assert result is False

    def test_cancelled_job_has_completed_at(self):
        from ollama_arena.finetuning.orchestrator import JobQueue
        q = JobQueue()
        job = _make_job("cancel_ts")
        q.enqueue(job)
        q.cancel_job("cancel_ts")
        assert job.completed_at is not None

    def test_list_jobs_limit(self):
        from ollama_arena.finetuning.orchestrator import JobQueue
        q = JobQueue()
        for i in range(10):
            q.enqueue(_make_job(f"j{i}"))
        result = q.list_jobs(limit=5)
        assert len(result) <= 5

    def test_update_job_result(self):
        from ollama_arena.finetuning.orchestrator import JobQueue
        q = JobQueue()
        job = _make_job("result_job")
        q.enqueue(job)
        q.update_job("result_job", result={"accuracy": 0.95})
        assert q.get_job("result_job").result == {"accuracy": 0.95}


# ──────────────────────────────────────────────────────────────────────────────
# FinetuningMonitor — DB operations
# ──────────────────────────────────────────────────────────────────────────────

class TestFinetuningMonitor:
    def _make(self, tmp_path):
        from ollama_arena.finetuning.orchestrator import FinetuningMonitor
        return FinetuningMonitor(db_path=str(tmp_path / "ft.db"))

    def test_init_does_not_crash(self, tmp_path):
        m = self._make(tmp_path)
        assert m is not None

    def test_callbacks_initially_empty(self, tmp_path):
        m = self._make(tmp_path)
        assert m._callbacks == []

    def test_record_job_start(self, tmp_path):
        from ollama_arena.finetuning.orchestrator import JobStatus
        m = self._make(tmp_path)
        job = _make_job("monitor_job")
        job.status = JobStatus.RUNNING
        m.record_job_start(job)  # Must not raise

    def test_record_job_complete_completed(self, tmp_path):
        from ollama_arena.finetuning.orchestrator import JobStatus
        m = self._make(tmp_path)
        job = _make_job("monitor_job2")
        job.status = JobStatus.RUNNING
        m.record_job_start(job)
        job.status = JobStatus.COMPLETED
        m.record_job_complete(job)  # Must not raise

    def test_record_job_complete_failed(self, tmp_path):
        from ollama_arena.finetuning.orchestrator import JobStatus
        m = self._make(tmp_path)
        job = _make_job("monitor_job3")
        job.status = JobStatus.FAILED
        job.error_message = "OOM error"
        m.record_job_start(job)
        m.record_job_complete(job)

    def test_get_job_history_no_crash(self, tmp_path):
        """get_job_history must work on an empty table (regression test for a fixed
        bug: it used to call cx.description on the Connection instead of the
        Cursor, which always raised AttributeError)."""
        m = self._make(tmp_path)
        history = m.get_job_history()
        assert history == []

    def test_get_job_history_returns_recorded_job(self, tmp_path):
        from ollama_arena.finetuning.orchestrator import JobStatus
        m = self._make(tmp_path)
        job = _make_job("history_job")
        job.status = JobStatus.RUNNING
        m.record_job_start(job)
        history = m.get_job_history()
        assert len(history) == 1
        assert history[0]["job_id"] == "history_job"
        assert history[0]["model"] == "llama3:8b"

    def test_register_callback(self, tmp_path):
        m = self._make(tmp_path)
        called = []
        def cb(event, data):
            called.append((event, data))
        m.register_callback(cb)
        assert len(m._callbacks) == 1


# ──────────────────────────────────────────────────────────────────────────────
# FinetuningOrchestrator.submit_job — job_id collision regression
# ──────────────────────────────────────────────────────────────────────────────

class TestSubmitJobIdCollision:
    def test_two_submissions_same_model_get_unique_ids(self, tmp_path):
        """Regression test: job_id was built from int(time.time()) plus a hash
        of the model name only, so two jobs submitted for the same model
        within the same second got an identical job_id. The second submit_job
        call would then raise RuntimeError because JobQueue.enqueue rejects
        duplicates."""
        from ollama_arena.finetuning.orchestrator import FinetuningOrchestrator
        orch = FinetuningOrchestrator(db_path=str(tmp_path / "arena.db"))
        job_id_1 = orch.submit_job("llama3:8b")
        job_id_2 = orch.submit_job("llama3:8b")
        assert job_id_1 != job_id_2
        assert orch.job_queue.get_job(job_id_1) is not None
        assert orch.job_queue.get_job(job_id_2) is not None
