"""Ollama native /api/generate client."""
from __future__ import annotations
import json, logging, re, time
import requests

from .base import GenResult

log = logging.getLogger("arena.backend.ollama")
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


class OllamaBackend:
    name = "ollama"

    def __init__(self, base_url: str = "http://localhost:11434", timeout: int = 180):
        self.base = base_url.rstrip("/")
        self.timeout = timeout

    def generate(self, model: str, prompt: str, **opts) -> GenResult:
        opts.setdefault("num_ctx", 4096)
        opts.setdefault("temperature", 0.0)
        opts.setdefault("num_predict", 1024)

        t0 = time.time()
        ttft = 0.0
        try:
            r = requests.post(
                f"{self.base}/api/generate",
                json={"model": model, "prompt": prompt, "stream": True, "options": opts},
                timeout=self.timeout, stream=True,
            )
            text = ""
            first = True
            tokens_in = tokens_out = 0
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if first and chunk.get("response"):
                    ttft = time.time() - t0
                    first = False
                text += chunk.get("response", "")
                if chunk.get("done"):
                    tokens_in  = chunk.get("prompt_eval_count", 0)
                    tokens_out = chunk.get("eval_count", 0)
                    break
            latency = time.time() - t0
            text = _THINK.sub("", text).strip()
            tps = tokens_out / latency if latency > 0 else 0.0
            return GenResult(
                text=text, model=model,
                tokens_in=tokens_in, tokens_out=tokens_out,
                latency_s=round(latency, 3), tps=round(tps, 1),
                time_to_first=round(ttft, 3),
            )
        except Exception as e:
            return GenResult(text="", model=model, error=str(e),
                             latency_s=round(time.time() - t0, 3))

    def list_models(self) -> list[str]:
        try:
            r = requests.get(f"{self.base}/api/tags", timeout=5)
            return [m["name"] for m in r.json().get("models", [])]
        except Exception:
            return []

    def is_alive(self) -> bool:
        try:
            requests.get(f"{self.base}/api/tags", timeout=3)
            return True
        except Exception:
            return False
