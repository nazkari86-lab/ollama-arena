"""Device selection for simulation training -- a thin pass-through to
finetuning.orchestrator.GPUAllocator's already-tested detection
(torch.cuda.is_available()/torch.backends.mps.is_available()), not a
second implementation of GPU detection.

Deliberately does NOT route through the full FinetuningOrchestrator job
queue: that orchestrator's worker thread/JobQueue/FinetuningMonitor are
shaped around long-running full-finetune jobs against arena.db, whereas
`sim train` is a synchronous, on-demand call (the same shape as `sim run`)
-- only the GPU-detection piece is actually relevant and reusable here.
"""
from __future__ import annotations

from ...finetuning.orchestrator import GPUAllocator, GPUType


def detect_device() -> str:
    """Best available device string for ImitationConfig.device.

    Defaults effectively to "cpu" (GPUAllocator always has a CPU fallback
    entry) -- callers must call this explicitly to opt in to GPU use; it
    is never assumed.
    """
    allocator = GPUAllocator()
    if any(g.gpu_type == GPUType.CUDA for g in allocator.gpus):
        return "cuda"
    if any(g.gpu_type == GPUType.MPS for g in allocator.gpus):
        return "mps"
    return "cpu"
