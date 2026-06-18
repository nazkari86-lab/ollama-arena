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
    # Speculative decoding llama-server ports
    8888:  "speculative",
    8889:  "speculative",
    8890:  "speculative",
    8891:  "speculative",
    8892:  "speculative",
    8893:  "speculative",
    8894:  "speculative",
    8895:  "speculative",
    8896:  "speculative",
    8897:  "speculative",
}


def detect_backend(url: str | None = None) -> str:
    """Guess backend type from a URL. Returns 'ollama', 'openai-compat', or 'speculative'."""
    if not url:
        return "ollama"
    u = urlparse(url)
    if u.port in _PORT_HINTS:
        kind = _PORT_HINTS[u.port]
        if kind == "ollama":
            return "ollama"
        if kind == "speculative":
            return "speculative"
        return "openai-compat"
    if "11434" in url:
        return "ollama"
    return "openai-compat"


def spec_backend_for_model(model: str) -> Backend | None:
    """Return a SpeculativeBackend if model is a spec: prefixed name, else None."""
    from .spec import is_spec_model, SpeculativeBackend, SPEC_SERVERS
    if is_spec_model(model) and model in SPEC_SERVERS:
        return SpeculativeBackend(model)
    return None


def auto_backend(url: str | None = None, api_key: str | None = None) -> Backend:
    """Return an appropriate backend based on `url` or backend name.

    Recognizes:
      - None / "ollama" / Ollama URL        → OllamaBackend
      - "anthropic" / api.anthropic.com     → AnthropicBackend (native protocol)
      - any OpenAI-compat preset name        → OpenAICompatBackend
      - other URL                            → OpenAICompatBackend
    """
    if not url:
        return OllamaBackend()

    # Native Anthropic backend — the compat shim breaks on streaming
    if url in ("anthropic", "claude") or "api.anthropic.com" in (url or ""):
        from .anthropic import AnthropicBackend
        return AnthropicBackend(api_key=api_key)

    if url in OpenAICompatBackend.PRESETS:
        return OpenAICompatBackend(base_url=url, api_key=api_key)

    if detect_backend(url) == "ollama":
        return OllamaBackend(base_url=url)
    return OpenAICompatBackend(base_url=url, api_key=api_key)
