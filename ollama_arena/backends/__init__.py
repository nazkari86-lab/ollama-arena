"""
Multi-backend support for LLM Arena.

Supports:
  • Ollama         — http://localhost:11434
  • OpenAI-compat  — vLLM, LM Studio, llama.cpp server, OpenAI, Groq, Together, OpenRouter
  • Transformers   — direct HuggingFace transformers (pytorch)
  • vLLM           — direct vLLM Python API for maximum throughput
"""
from .base import Backend, GenResult
from .ollama import OllamaBackend
from .openai_compat import OpenAICompatBackend
from .auto import auto_backend, detect_backend

__all__ = [
    "Backend", "GenResult",
    "OllamaBackend", "OpenAICompatBackend",
    "auto_backend", "detect_backend",
]
