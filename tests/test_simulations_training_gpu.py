"""gpu.py: must be a pure pass-through to finetuning.orchestrator's already-
tested GPU detection -- no GPU-detection logic should be duplicated here."""
from unittest.mock import MagicMock, patch

from ollama_arena.finetuning.orchestrator import GPUResource, GPUType
from ollama_arena.simulations.training.gpu import detect_device


def _mock_allocator(gpus):
    instance = MagicMock()
    instance.gpus = gpus
    return instance


def test_detect_device_returns_cuda_when_available():
    cuda_gpu = GPUResource(gpu_id=0, gpu_type=GPUType.CUDA, total_memory_gb=24, available_memory_gb=24)
    with patch("ollama_arena.simulations.training.gpu.GPUAllocator", return_value=_mock_allocator([cuda_gpu])):
        assert detect_device() == "cuda"


def test_detect_device_returns_mps_when_no_cuda():
    mps_gpu = GPUResource(gpu_id=0, gpu_type=GPUType.MPS, total_memory_gb=16, available_memory_gb=16)
    with patch("ollama_arena.simulations.training.gpu.GPUAllocator", return_value=_mock_allocator([mps_gpu])):
        assert detect_device() == "mps"


def test_detect_device_falls_back_to_cpu():
    cpu_only = GPUResource(gpu_id=0, gpu_type=GPUType.CPU, total_memory_gb=8, available_memory_gb=8)
    with patch("ollama_arena.simulations.training.gpu.GPUAllocator", return_value=_mock_allocator([cpu_only])):
        assert detect_device() == "cpu"


def test_detect_device_prefers_cuda_over_mps_if_both_present():
    """Shouldn't realistically happen on real hardware, but the priority
    order (cuda > mps > cpu) must be deterministic regardless."""
    cuda_gpu = GPUResource(gpu_id=0, gpu_type=GPUType.CUDA, total_memory_gb=24, available_memory_gb=24)
    mps_gpu = GPUResource(gpu_id=1, gpu_type=GPUType.MPS, total_memory_gb=16, available_memory_gb=16)
    with patch("ollama_arena.simulations.training.gpu.GPUAllocator", return_value=_mock_allocator([cuda_gpu, mps_gpu])):
        assert detect_device() == "cuda"


def test_detect_device_uses_real_allocator_without_crashing():
    """Smoke test against the real (unmocked) GPUAllocator -- whatever this
    machine actually has, detect_device() must return a valid string."""
    assert detect_device() in ("cuda", "mps", "cpu")
