"""Ollama native /api/generate + /api/chat client."""
from __future__ import annotations
import json, logging, re, time
from datetime import date
import requests

from .base import GenResult, ChatTurnResult

log = logging.getLogger("arena.backend.ollama")
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

_SYSTEM_PROMPT = (
    "You are a helpful, accurate assistant. "
    "Today's date is {date}. "
    "Use this date when answering questions about current events, rankings, or time-sensitive information. "
    "Do not claim your knowledge cutoff is the current date — acknowledge that your training data "
    "has a cutoff and that information may have changed since then."
)


def _system_message() -> dict:
    return {"role": "system", "content": _SYSTEM_PROMPT.format(date=date.today().isoformat())}


def _inject_system(messages: list[dict]) -> list[dict]:
    """Prepend system message if not already present."""
    if messages and messages[0].get("role") == "system":
        return messages
    return [_system_message()] + messages


class OllamaBackend:
    name = "ollama"

    def __init__(self, base_url: str = "http://localhost:11434", timeout: int = 180):
        self.base = base_url.rstrip("/")
        self.timeout = timeout

    def generate(self, model: str, prompt: str, **opts) -> GenResult:
        messages = _inject_system([{"role": "user", "content": prompt}])
        return self._chat(model, messages, tools=[], **opts)

    def generate_with_tools(self, model: str, messages: list[dict], tools: list[dict], **opts) -> GenResult:
        messages = _inject_system(messages)
        result = self._chat(model, messages, tools=tools, **opts)
        return result

    def chat_turn(self, model: str, messages: list[dict], tools: list[dict], **opts) -> ChatTurnResult:
        """One /api/chat turn — used by the agent loop for multi-step tool use."""
        messages = _inject_system(messages)
        call_timeout = opts.pop("_timeout", None) or self.timeout
        body: dict = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": opts.get("temperature", 0.0),
                "num_predict": opts.get("num_predict", 1024),
                "num_ctx": opts.get("num_ctx", 4096),
            },
        }
        if tools:
            body["tools"] = tools

        t0 = time.time()
        ttft = 0.0
        text = ""
        tool_calls: list[dict] = []
        finish_reason = "stop"
        tokens_in = tokens_out = 0
        first = True
        try:
            r = requests.post(
                f"{self.base}/api/chat",
                json=body, stream=True, timeout=call_timeout,
            )
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = chunk.get("message", {})
                content = msg.get("content", "")
                if first and content:
                    ttft = time.time() - t0
                    first = False
                text += content
                # Collect tool calls (Ollama returns them in message.tool_calls)
                for tc in msg.get("tool_calls") or []:
                    tool_calls.append(tc)
                if chunk.get("done"):
                    tokens_in  = chunk.get("prompt_eval_count", 0)
                    tokens_out = chunk.get("eval_count", 0)
                    finish_reason = "tool_calls" if tool_calls else "stop"
                    break
        except Exception as e:
            return ChatTurnResult(error=str(e), latency_s=round(time.time() - t0, 3))

        latency = time.time() - t0
        text = _THINK.sub("", text).strip()
        return ChatTurnResult(
            text=text,
            tool_calls=tool_calls,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_s=round(latency, 3),
            time_to_first=round(ttft, 3),
            finish_reason=finish_reason,
        )

    def _chat(self, model: str, messages: list[dict], tools: list[dict], **opts) -> GenResult:
        """Single-shot /api/chat call (no agentic loop)."""
        call_timeout = opts.pop("_timeout", None) or self.timeout
        body: dict = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": opts.get("temperature", 0.0),
                "num_predict": opts.get("num_predict", 1024),
                "num_ctx": opts.get("num_ctx", 4096),
            },
        }
        if tools:
            body["tools"] = tools

        t0 = time.time()
        ttft = 0.0
        text = ""
        tool_calls: list[dict] = []
        tokens_in = tokens_out = 0
        first = True
        try:
            r = requests.post(
                f"{self.base}/api/chat",
                json=body, stream=True, timeout=call_timeout,
            )
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = chunk.get("message", {})
                content = msg.get("content", "")
                if first and content:
                    ttft = time.time() - t0
                    first = False
                text += content
                for tc in msg.get("tool_calls") or []:
                    tool_calls.append(tc)
                if chunk.get("done"):
                    tokens_in  = chunk.get("prompt_eval_count", 0)
                    tokens_out = chunk.get("eval_count", 0)
                    break
        except Exception as e:
            return GenResult(text="", model=model, error=str(e),
                             latency_s=round(time.time() - t0, 3))

        latency = time.time() - t0
        text = _THINK.sub("", text).strip()
        tps = tokens_out / latency if latency > 0 else 0.0
        return GenResult(
            text=text, model=model,
            tokens_in=tokens_in, tokens_out=tokens_out,
            latency_s=round(latency, 3), tps=round(tps, 1),
            time_to_first=round(ttft, 3),
            tool_calls=tool_calls,
        )

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
