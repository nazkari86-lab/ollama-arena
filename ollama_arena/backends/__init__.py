"""Adapters to model servers and runtimes."""
from .base import Backend, GenResult
from .ollama import OllamaBackend
from .openai_compat import OpenAICompatBackend
from .auto import auto_backend, detect_backend
from .spec import SpeculativeBackend, SpecManager, SPEC_SERVERS, is_spec_model


def _lazy_transformers():
    """Importing transformers at module load is expensive and optional."""
    from .transformers_backend import TransformersBackend
    return TransformersBackend


__all__ = [
    "Backend", "GenResult",
    "OllamaBackend", "OpenAICompatBackend",
    "auto_backend", "detect_backend",
    "SpeculativeBackend", "SpecManager", "SPEC_SERVERS", "is_spec_model",
]
