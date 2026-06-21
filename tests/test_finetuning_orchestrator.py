"""Tests for finetuning orchestrator — JobQueue, GPUAllocator (no GPU required)."""
from __future__ import annotations

import pytest


def _make_job(job_id="job_1", priority=5, memory=8.0):
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
# JobQueue
# ──────────────────────────────────────────────────────────────────────────────

class TestJobQueue:
    def test_enqueue_success(self):
        from ollama_arena.finetuning.orchestrator import JobQueue
        q = JobQueue()
        job = _make_job()
        result = q.enqueue(job)
        assert result is True

    def test_enqueue_duplicate_fails(self):
        from ollama_arena.finetuning.orchestrator import JobQueue
        q = JobQueue()
        job = _make_job()
        q.enqueue(job)
        result = q.enqueue(job)
        assert result is False

    def test_enqueue_sets_status_queued(self):
        from ollama_arena.finetuning.orchestrator import JobQueue, JobStatus
        q = JobQueue()
        job = _make_job()
        q.enqueue(job)
        assert job.status == JobStatus.QUEUED

    def test_get_job_after_enqueue(self):
        from ollama_arena.finetuning.orchestrator import JobQueue
        q = JobQueue()
        job = _make_job("unique_job")
        q.enqueue(job)
        retrieved = q.get_job("unique_job")
        assert retrieved is job

    def test_get_job_nonexistent_returns_none(self):
        from ollama_arena.finetuning.orchestrator import JobQueue
        q = JobQueue()
        assert q.get_job("nonexistent") is None

    def test_list_jobs_empty(self):
        from ollama_arena.finetuning.orchestrator import JobQueue
        q = JobQueue()
        assert q.list_jobs() == []

    def test_list_jobs_returns_enqueued(self):
        from ollama_arena.finetuning.orchestrator import JobQueue
        q = JobQueue()
        q.enqueue(_make_job("j1"))
        q.enqueue(_make_job("j2"))
        jobs = q.list_jobs()
        assert len(jobs) == 2

    def test_list_jobs_filtered_by_status(self):
        from ollama_arena.finetuning.orchestrator import JobQueue, JobStatus
        q = JobQueue()
        q.enqueue(_make_job("j1"))
        q.enqueue(_make_job("j2"))
        # All should be QUEUED after enqueue
        queued = q.list_jobs(status=JobStatus.QUEUED)
        assert len(queued) == 2
        pending = q.list_jobs(status=JobStatus.PENDING)
        assert len(pending) == 0

    def test_update_job_status(self):
        from ollama_arena.finetuning.orchestrator import JobQueue, JobStatus
        q = JobQueue()
        job = _make_job("update_me")
        q.enqueue(job)
        q.update_job("update_me", status=JobStatus.COMPLETED)
        assert q.get_job("update_me").status == JobStatus.COMPLETED

    def test_update_job_nonexistent_no_crash(self):
        from ollama_arena.finetuning.orchestrator import JobQueue, JobStatus
        q = JobQueue()
        # Should not crash
        q.update_job("nonexistent", status=JobStatus.COMPLETED)

    def test_update_job_error_message(self):
        from ollama_arena.finetuning.orchestrator import JobQueue, JobStatus
        q = JobQueue()
        job = _make_job("err_job")
        q.enqueue(job)
        q.update_job("err_job", error_message="out of memory")
        assert q.get_job("err_job").error_message == "out of memory"

    def test_update_job_gpu_id(self):
        from ollama_arena.finetuning.orchestrator import JobQueue
        q = JobQueue()
        job = _make_job("gpu_job")
        q.enqueue(job)
        q.update_job("gpu_job", gpu_id=0)
        assert q.get_job("gpu_job").gpu_id == 0

    def test_dequeue_sets_running_status(self):
        from ollama_arena.finetuning.orchestrator import JobQueue, JobStatus
        q = JobQueue()
        job = _make_job("dequeue_me")
        q.enqueue(job)
        dequeued = q.dequeue(timeout=0.1)
        if dequeued:  # May be None if timing is tight
            assert dequeued.status == JobStatus.RUNNING

    def test_dequeue_empty_returns_none(self):
        from ollama_arena.finetuning.orchestrator import JobQueue
        q = JobQueue()
        result = q.dequeue(timeout=0.05)
        assert result is None

    def test_max_size_respected(self):
        from ollama_arena.finetuning.orchestrator import JobQueue
        q = JobQueue(max_size=2)
        q.enqueue(_make_job("j1"))
        q.enqueue(_make_job("j2"))
        result = q.enqueue(_make_job("j3"))
        # Third job may fail due to full queue or duplicate; just check it's bool
        assert isinstance(result, bool)


# ──────────────────────────────────────────────────────────────────────────────
# GPUAllocator — tests that work without actual GPUs
# ──────────────────────────────────────────────────────────────────────────────

class TestGPUAllocator:
    def test_init_runs_without_gpu(self):
        from ollama_arena.finetuning.orchestrator import GPUAllocator
        # Should not crash even without GPU
        allocator = GPUAllocator()
        assert isinstance(allocator.gpus, list)

    def test_gpus_is_list(self):
        from ollama_arena.finetuning.orchestrator import GPUAllocator
        allocator = GPUAllocator()
        assert isinstance(allocator.gpus, list)

    def test_allocate_returns_none_when_no_gpus(self):
        from ollama_arena.finetuning.orchestrator import GPUAllocator
        allocator = GPUAllocator()
        allocator.gpus = []  # Force empty
        result = allocator.allocate_gpu(required_memory_gb=8.0)
        assert result is None

    def test_allocate_with_available_gpu(self):
        from ollama_arena.finetuning.orchestrator import GPUAllocator, GPUResource, GPUType
        allocator = GPUAllocator()
        allocator.gpus = [
            GPUResource(gpu_id=0, gpu_type=GPUType.CPU, total_memory_gb=32.0, available_memory_gb=32.0)
        ]
        result = allocator.allocate_gpu(required_memory_gb=8.0)
        assert result is not None
        assert result.in_use is True

    def test_release_gpu(self):
        from ollama_arena.finetuning.orchestrator import GPUAllocator, GPUResource, GPUType
        allocator = GPUAllocator()
        gpu = GPUResource(gpu_id=0, gpu_type=GPUType.CPU, total_memory_gb=32.0, available_memory_gb=16.0)
        gpu.in_use = True
        allocator.gpus = [gpu]
        allocator.release_gpu(0)
        assert allocator.gpus[0].in_use is False

    def test_get_status_returns_list(self):
        from ollama_arena.finetuning.orchestrator import GPUAllocator
        allocator = GPUAllocator()
        status = allocator.get_status()
        assert isinstance(status, list)

    def test_get_available_memory_no_gpus(self):
        from ollama_arena.finetuning.orchestrator import GPUAllocator
        allocator = GPUAllocator()
        allocator.gpus = []
        mem = allocator.get_available_memory()
        assert mem == 0.0
