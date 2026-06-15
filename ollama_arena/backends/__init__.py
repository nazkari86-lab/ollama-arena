"""
Backends — adapters to model servers and runtimes.

    OllamaBackend         http://localhost:11434
    OpenAICompatBackend   vLLM, LM Studio, llama.cpp, OpenAI, Groq, ...
    TransformersBackend   in-process HuggingFace transformers (lazy)
"""
from .base import Backend, GenResult
from .ollama import OllamaBackend
from .openai_compat import OpenAICompatBackend
from .auto import auto_backend, detect_backend


def _lazy_transformers():
    """Importing transformers at module load is expensive and optional."""
    from .transformers_backend import TransformersBackend
    return TransformersBackend


__all__ = [
    "Backend", "GenResult",
    "OllamaBackend", "OpenAICompatBackend",
    "auto_backend", "detect_backend",
]
