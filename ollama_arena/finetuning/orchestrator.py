"""Finetuning Orchestration - GPU resource management and job scheduling."""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional, List, Dict, Callable
from queue import Queue, Empty
import hashlib
import uuid

from .unsloth_integration import FinetuneTrigger, TriggerType

log = logging.getLogger("arena.finetuning.orchestrator")


class JobStatus(Enum):
    """Status of a finetuning job."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GPUType(Enum):
    """Types of GPU resources."""
    CUDA = "cuda"
    MPS = "mps"  # Apple Silicon
    CPU = "cpu"


@dataclass
class GPUResource:
    """GPU resource description."""
    gpu_id: int
    gpu_type: GPUType
    total_memory_gb: float
    available_memory_gb: float
    compute_capability: Optional[str] = None
    in_use: bool = False
    current_job_id: Optional[str] = None


@dataclass
class FinetuningJob:
    """A finetuning job in the queue."""
    job_id: str
    model: str
    category: Optional[str]
    status: JobStatus
    priority: int  # Higher = more important
    estimated_gpu_memory_gb: float
    estimated_duration_minutes: float
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    gpu_id: Optional[int] = None
    trigger_type: Optional[str] = None
    dataset_version: Optional[str] = None
    error_message: Optional[str] = None
    result: Optional[Dict] = None
    metadata: Dict = field(default_factory=dict)


class GPUAllocator:
    """Manage GPU resource allocation for finetuning jobs."""

    def __init__(self):
        self.gpus: List[GPUResource] = []
        self._lock = threading.Lock()
        self._detect_gpus()

    def _detect_gpus(self):
        """Detect available GPUs."""
        try:
            # Try CUDA
            import torch
            if torch.cuda.is_available():
                num_gpus = torch.cuda.device_count()
                for i in range(num_gpus):
                    props = torch.cuda.get_device_properties(i)
                    total_mem = props.total_memory / (1024 ** 3)  # Convert to GB
                    self.gpus.append(GPUResource(
                        gpu_id=i,
                        gpu_type=GPUType.CUDA,
                        total_memory_gb=total_mem,
                        available_memory_gb=total_mem,
                        compute_capability=f"{props.major}.{props.minor}",
                    ))
                log.info(f"[gpu] Detected {num_gpus} CUDA GPUs")
            else:
                # Try MPS (Apple Silicon)
                if torch.backends.mps.is_available():
                    self.gpus.append(GPUResource(
                        gpu_id=0,
                        gpu_type=GPUType.MPS,
                        total_memory_gb=16.0,  # Estimate
                        available_memory_gb=16.0,
                    ))
                    log.info("[gpu] Detected MPS (Apple Silicon)")
                else:
                    # CPU fallback
                    self.gpus.append(GPUResource(
                        gpu_id=0,
                        gpu_type=GPUType.CPU,
                        total_memory_gb=8.0,  # System RAM estimate
                        available_memory_gb=8.0,
                    ))
                    log.info("[gpu] Using CPU (no GPU detected)")
        except ImportError:
            # CPU fallback if torch not available
            self.gpus.append(GPUResource(
                gpu_id=0,
                gpu_type=GPUType.CPU,
                total_memory_gb=8.0,
                available_memory_gb=8.0,
            ))
            log.warning("[gpu] PyTorch not available, using CPU")

    def allocate_gpu(
        self,
        required_memory_gb: float,
        preferred_type: Optional[GPUType] = None,
    ) -> Optional[GPUResource]:
        """
        Allocate a GPU for a job.

        Returns None if no suitable GPU available.
        """
        with self._lock:
            candidates = []
            for gpu in self.gpus:
                if gpu.in_use:
                    continue
                if preferred_type and gpu.gpu_type != preferred_type:
                    continue
                if gpu.available_memory_gb >= required_memory_gb:
                    candidates.append(gpu)

            if not candidates:
                return None

            # Prefer GPU with least wasted memory
            candidates.sort(key=lambda g: g.available_memory_gb)
            gpu = candidates[0]

            # Mark as in use
            gpu.in_use = True
            return gpu

    def release_gpu(self, gpu_id: int):
        """Release a GPU resource."""
        with self._lock:
            for gpu in self.gpus:
                if gpu.gpu_id == gpu_id:
                    gpu.in_use = False
                    gpu.current_job_id = None
                    log.info(f"[gpu] Released GPU {gpu_id}")
                    return

    def get_available_memory(self, gpu_type: Optional[GPUType] = None) -> float:
        """Get total available memory across GPUs."""
        with self._lock:
            total = 0.0
            for gpu in self.gpus:
                if not gpu.in_use:
                    if gpu_type is None or gpu.gpu_type == gpu_type:
                        total += gpu.available_memory_gb
            return total

    def get_status(self) -> List[Dict]:
        """Get status of all GPUs."""
        with self._lock:
            return [
                {
                    "gpu_id": g.gpu_id,
                    "type": g.gpu_type.value,
                    "total_memory_gb": g.total_memory_gb,
                    "available_memory_gb": g.available_memory_gb,
                    "in_use": g.in_use,
                    "current_job_id": g.current_job_id,
                }
                for g in self.gpus
            ]


class JobQueue:
    """Thread-safe job queue for finetuning."""

    def __init__(self, max_size: int = 100):
        self._queue: Queue[FinetuningJob] = Queue(maxsize=max_size)
        self._jobs: Dict[str, FinetuningJob] = {}
        self._lock = threading.Lock()

    def enqueue(self, job: FinetuningJob) -> bool:
        """Add a job to the queue."""
        with self._lock:
            if job.job_id in self._jobs:
                log.warning(f"[queue] Job {job.job_id} already exists")
                return False

            try:
                self._queue.put(job, block=False)
                self._jobs[job.job_id] = job
                job.status = JobStatus.QUEUED
                log.info(f"[queue] Enqueued job {job.job_id}")
                return True
            except Exception:
                log.error("[queue] Queue is full")
                return False

    def requeue(self, job: FinetuningJob) -> bool:
        """Put a previously-dequeued job back on the queue.

        Unlike enqueue(), this does not reject jobs already tracked in
        self._jobs — a job that was dequeued for execution is still in
        _jobs (it's only removed from the internal Queue), so routing it
        through enqueue() would always be rejected as a duplicate and the
        job would be silently dropped (stuck in RUNNING forever).
        """
        with self._lock:
            try:
                self._queue.put(job, block=False)
                self._jobs[job.job_id] = job
                job.status = JobStatus.QUEUED
                log.info(f"[queue] Re-queued job {job.job_id}")
                return True
            except Exception:
                log.error(f"[queue] Failed to re-queue job {job.job_id} — queue is full")
                return False

    def dequeue(self, timeout: float = 1.0) -> Optional[FinetuningJob]:
        """Get the next job from the queue."""
        try:
            job = self._queue.get(block=True, timeout=timeout)
            with self._lock:
                job.status = JobStatus.RUNNING
                job.started_at = datetime.now().isoformat()
            return job
        except Empty:
            return None

    def update_job(
        self,
        job_id: str,
        status: Optional[JobStatus] = None,
        gpu_id: Optional[int] = None,
        error_message: Optional[str] = None,
        result: Optional[Dict] = None,
    ):
        """Update job status."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return

            if status:
                job.status = status
                if status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                    job.completed_at = datetime.now().isoformat()
            if gpu_id is not None:
                job.gpu_id = gpu_id
            if error_message:
                job.error_message = error_message
            if result:
                job.result = result

    def get_job(self, job_id: str) -> Optional[FinetuningJob]:
        """Get a job by ID."""
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        limit: int = 50,
    ) -> List[FinetuningJob]:
        """List jobs, optionally filtered by status."""
        with self._lock:
            jobs = list(self._jobs.values())

            if status:
                jobs = [j for j in jobs if j.status == status]

            # Sort by priority (descending) and created_at (descending)
            jobs.sort(key=lambda j: (-j.priority, j.created_at), reverse=False)

            return jobs[:limit]

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False

            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                return False

            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now().isoformat()
            return True


class FinetuningMonitor:
    """Monitor finetuning jobs and provide progress updates."""

    def __init__(self, db_path: str = "arena.db"):
        self.db_path = db_path
        self._callbacks: List[Callable[[str, Dict], None]] = []
        self._ensure_table()

    def _ensure_table(self):
        """Ensure the finetuning_jobs table exists."""
        with sqlite3.connect(self.db_path) as cx:
            cx.execute("""
                CREATE TABLE IF NOT EXISTS finetuning_jobs (
                    job_id TEXT PRIMARY KEY,
                    model TEXT NOT NULL,
                    category TEXT,
                    status TEXT NOT NULL,
                    priority INTEGER,
                    estimated_gpu_memory_gb REAL,
                    estimated_duration_minutes REAL,
                    created_at REAL,
                    started_at REAL,
                    completed_at REAL,
                    gpu_id INTEGER,
                    trigger_type TEXT,
                    dataset_version TEXT,
                    error_message TEXT,
                    result TEXT,
                    metadata TEXT
                )
            """)

    def record_job_start(self, job: FinetuningJob):
        """Record job start in database."""
        with sqlite3.connect(self.db_path) as cx:
            cx.execute("""
                INSERT INTO finetuning_jobs
                (job_id, model, category, status, priority,
                 estimated_gpu_memory_gb, estimated_duration_minutes,
                 created_at, started_at, gpu_id, trigger_type,
                 dataset_version, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.job_id,
                job.model,
                job.category,
                job.status.value,
                job.priority,
                job.estimated_gpu_memory_gb,
                job.estimated_duration_minutes,
                datetime.fromisoformat(job.created_at).timestamp(),
                datetime.fromisoformat(job.started_at).timestamp() if job.started_at else None,
                job.gpu_id,
                job.trigger_type,
                job.dataset_version,
                json.dumps(job.metadata),
            ))

        self._notify_callbacks("job_started", {"job_id": job.job_id})

    def record_job_complete(self, job: FinetuningJob):
        """Record job completion in database."""
        with sqlite3.connect(self.db_path) as cx:
            cx.execute("""
                UPDATE finetuning_jobs
                SET status = ?, completed_at = ?, gpu_id = ?,
                    error_message = ?, result = ?
                WHERE job_id = ?
            """, (
                job.status.value,
                datetime.fromisoformat(job.completed_at).timestamp() if job.completed_at else None,
                job.gpu_id,
                job.error_message,
                json.dumps(job.result) if job.result else None,
                job.job_id,
            ))

        self._notify_callbacks("job_completed", {
            "job_id": job.job_id,
            "status": job.status.value,
        })

    def get_job_history(
        self,
        model: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """Get finetuning job history."""
        query = "SELECT * FROM finetuning_jobs"
        params: List[Any] = []

        if model:
            query += " WHERE model = ?"
            params.append(model)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(self.db_path) as cx:
            cursor = cx.execute(query, params)
            rows = cursor.fetchall()
            cols = [desc[0] for desc in cursor.description]

            history = []
            for row in rows:
                info = dict(zip(cols, row))
                if info.get("result"):
                    info["result"] = json.loads(info["result"])
                if info.get("metadata"):
                    info["metadata"] = json.loads(info["metadata"])
                history.append(info)

            return history

    def register_callback(self, callback: Callable[[str, Dict], None]):
        """Register a callback for job events."""
        self._callbacks.append(callback)

    def _notify_callbacks(self, event: str, data: Dict):
        """Notify all registered callbacks."""
        for callback in self._callbacks:
            try:
                callback(event, data)
            except Exception as e:
                log.error(f"Callback error: {e}")


class FinetuningOrchestrator:
    """Main orchestrator for finetuning jobs."""

    def __init__(
        self,
        db_path: str = "arena.db",
        max_concurrent_jobs: int = 1,
    ):
        self.db_path = db_path
        self.gpu_allocator = GPUAllocator()
        self.job_queue = JobQueue()
        self.monitor = FinetuningMonitor(db_path=db_path)
        self.max_concurrent_jobs = max_concurrent_jobs
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None

        # Import integrations
        from .dpo_pipeline import DPOPipeline
        from .unsloth_integration import AutoUnslothIntegrator

        self.dpo_pipeline = DPOPipeline(db_path=db_path)
        self.unsloth_integrator = AutoUnslothIntegrator(db_path=db_path)

    def start(self):
        """Start the orchestrator worker thread."""
        if self._running:
            return

        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        log.info("[orchestrator] Started")

    def stop(self):
        """Stop the orchestrator worker thread."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5.0)
        log.info("[orchestrator] Stopped")

    def _worker_loop(self):
        """Main worker loop for processing jobs."""
        while self._running:
            job = self.job_queue.dequeue(timeout=1.0)

            if not job:
                continue

            # Check GPU availability
            gpu = self.gpu_allocator.allocate_gpu(job.estimated_gpu_memory_gb)
            if not gpu:
                # Put job back in queue (it's already tracked in _jobs from
                # the original enqueue, so use requeue() not enqueue())
                self.job_queue.requeue(job)
                time.sleep(5.0)
                continue

            # Update job with GPU assignment
            self.job_queue.update_job(job.job_id, gpu_id=gpu.gpu_id)
            gpu.current_job_id = job.job_id

            # Record start
            self.monitor.record_job_start(job)

            # Execute job
            try:
                trigger = FinetuneTrigger(
                    trigger_type=TriggerType(job.trigger_type or "manual"),
                    threshold=0.0,
                    enabled=True,
                )

                result = self.unsloth_integrator.autofinetune(
                    model=job.model,
                    trigger=trigger,
                    category=job.category,
                )

                if result.success:
                    self.job_queue.update_job(
                        job.job_id,
                        status=JobStatus.COMPLETED,
                        result={
                            "ollama_name": result.ollama_name,
                            "adapter_dir": result.adapter_dir,
                            "gguf_path": result.gguf_path,
                            "training_time_seconds": result.training_time_seconds,
                        },
                    )
                else:
                    self.job_queue.update_job(
                        job.job_id,
                        status=JobStatus.FAILED,
                        error_message=result.error_message,
                    )

            except Exception as e:
                log.error(f"[orchestrator] Job {job.job_id} failed: {e}")
                self.job_queue.update_job(
                    job.job_id,
                    status=JobStatus.FAILED,
                    error_message=str(e),
                )

            finally:
                # Release GPU
                self.gpu_allocator.release_gpu(gpu.gpu_id)
                job = self.job_queue.get_job(job.job_id)
                if job:
                    self.monitor.record_job_complete(job)

    def submit_job(
        self,
        model: str,
        category: Optional[str] = None,
        priority: int = 5,
        estimated_gpu_memory_gb: float = 8.0,
        estimated_duration_minutes: float = 30.0,
        trigger_type: str = "manual",
    ) -> str:
        """
        Submit a finetuning job.

        Returns:
            Job ID
        """
        # uuid4 suffix avoids collisions when two jobs for the same model are
        # submitted within the same second (timestamp+model-hash alone would
        # produce identical IDs and the second submission would be silently
        # rejected as a duplicate by JobQueue.enqueue).
        job_id = (
            f"ft_{int(time.time())}_"
            f"{hashlib.sha256(model.encode()).hexdigest()[:8]}_"
            f"{uuid.uuid4().hex[:8]}"
        )

        job = FinetuningJob(
            job_id=job_id,
            model=model,
            category=category,
            status=JobStatus.PENDING,
            priority=priority,
            estimated_gpu_memory_gb=estimated_gpu_memory_gb,
            estimated_duration_minutes=estimated_duration_minutes,
            created_at=datetime.now().isoformat(),
            trigger_type=trigger_type,
        )

        if self.job_queue.enqueue(job):
            return job_id
        else:
            raise RuntimeError("Failed to enqueue job")

    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status."""
        return {
            "queued": len(self.job_queue.list_jobs(JobStatus.QUEUED)),
            "running": len(self.job_queue.list_jobs(JobStatus.RUNNING)),
            "completed": len(self.job_queue.list_jobs(JobStatus.COMPLETED)),
            "failed": len(self.job_queue.list_jobs(JobStatus.FAILED)),
            "gpu_status": self.gpu_allocator.get_status(),
        }

    def check_auto_finetune(self, model: str) -> Dict[str, Any]:
        """
        Check if a model should be auto-finetuned.

        Returns:
            Dict with should_finetune bool and trigger info
        """
        should, trigger, reason = self.unsloth_integrator.should_finetune(model)

        if should and trigger:
            # Auto-submit job
            job_id = self.submit_job(
                model=model,
                trigger_type=trigger.trigger_type.value,
                priority=10,  # High priority for auto-triggered
            )
            return {
                "should_finetune": True,
                "trigger_type": trigger.trigger_type.value,
                "reason": reason,
                "job_id": job_id,
            }

        return {
            "should_finetune": False,
            "trigger_type": None,
            "reason": reason,
            "job_id": None,
        }
