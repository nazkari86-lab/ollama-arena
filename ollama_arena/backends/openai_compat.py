"""
OpenAI-compatible backend.

Works with anything that speaks OpenAI's /v1/chat/completions:
  • vLLM            (--port 8000)
  • LM Studio       (default port 1234)
  • llama.cpp server
  • OpenAI          api.openai.com/v1
  • Groq            api.groq.com/openai/v1
  • Together        api.together.xyz/v1
  • OpenRouter      openrouter.ai/api/v1
  • Anything else with /v1/chat/completions
"""
from __future__ import annotations
import json, logging, os, re, time
import requests

from .base import GenResult

log = logging.getLogger("arena.backend.openai")
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


class OpenAICompatBackend:
    name = "openai-compat"

    # Convenience presets
    PRESETS: dict[str, str] = {
        "vllm":       "http://localhost:8000/v1",
        "lmstudio":   "http://localhost:1234/v1",
        "llamacpp":   "http://localhost:8080/v1",
        "openai":     "https://api.openai.com/v1",
        "groq":       "https://api.groq.com/openai/v1",
        "together":   "https://api.together.xyz/v1",
        "openrouter": "https://openrouter.ai/api/v1",
        "deepinfra":  "https://api.deepinfra.com/v1/openai",
        "fireworks":  "https://api.fireworks.ai/inference/v1",
    }

    def __init__(self, base_url: str = "http://localhost:8000/v1",
                 api_key: str | None = None, timeout: int = 180):
        # Resolve preset names
        if base_url in self.PRESETS:
            base_url = self.PRESETS[base_url]
        self.base = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "EMPTY")
        self.timeout = timeout
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/json",
        }

    def generate(self, model: str, prompt: str, **opts) -> GenResult:
        body = {
            "model":       model,
            "messages":    [{"role": "user", "content": prompt}],
            "temperature": opts.get("temperature", 0.0),
            "max_tokens":  opts.get("num_predict", opts.get("max_tokens", 1024)),
            "stream":      True,
        }
        t0 = time.time()
        ttft = 0.0
        text = ""
        first = True
        tokens_in = tokens_out = 0
        try:
            r = requests.post(
                f"{self.base}/chat/completions",
                json=body, headers=self._headers, stream=True, timeout=self.timeout,
            )
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                # Usage info (some providers emit on the last chunk)
                if (usage := chunk.get("usage")):
                    tokens_in  = usage.get("prompt_tokens", tokens_in)
                    tokens_out = usage.get("completion_tokens", tokens_out)
                # Delta content
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                piece = delta.get("content", "") or ""
                if first and piece:
                    ttft = time.time() - t0
                    first = False
                text += piece
            latency = time.time() - t0
            text = _THINK.sub("", text).strip()
            tps = tokens_out / latency if latency > 0 and tokens_out > 0 else (
                len(text.split()) * 1.3 / latency if latency > 0 else 0.0
            )
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
            r = requests.get(f"{self.base}/models", headers=self._headers, timeout=5)
            data = r.json().get("data", [])
            return [m["id"] for m in data]
        except Exception:
            return []

    def is_alive(self) -> bool:
        try:
            r = requests.get(f"{self.base}/models", headers=self._headers, timeout=3)
            return r.status_code < 500
        except Exception:
            return False
