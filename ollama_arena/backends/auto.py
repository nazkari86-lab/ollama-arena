"""Heuristic backend picker."""
from __future__ import annotations
import logging
from urllib.parse import urlparse

from .base import Backend
from .ollama import OllamaBackend
from .openai_compat import OpenAICompatBackend

log = logging.getLogger("arena.backend.auto")

# Known port → backend type
_PORT_HINTS = {
    11434: "ollama",
    8000:  "vllm",
    1234:  "lmstudio",
    8080:  "llamacpp",
}


def detect_backend(url: str | None = None) -> str:
    """Guess backend type from a URL. Returns 'ollama' or 'openai-compat'."""
    if not url:
        return "ollama"
    u = urlparse(url)
    if u.port in _PORT_HINTS:
        kind = _PORT_HINTS[u.port]
        return "ollama" if kind == "ollama" else "openai-compat"
    if "11434" in url:
        return "ollama"
    return "openai-compat"


def auto_backend(url: str | None = None, api_key: str | None = None) -> Backend:
    """Return an Ollama or OpenAI-compat backend based on `url`."""
    if not url:
        return OllamaBackend()

    if url in OpenAICompatBackend.PRESETS:
        return OpenAICompatBackend(base_url=url, api_key=api_key)

    if detect_backend(url) == "ollama":
        return OllamaBackend(base_url=url)
    return OpenAICompatBackend(base_url=url, api_key=api_key)
