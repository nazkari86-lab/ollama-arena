"""Ollama native /api/chat client (with tool support and date injection)."""
from __future__ import annotations
import json
import logging
import time
import requests

from .base import GenResult, ChatTurnResult, strip_thinking, inject_system

log = logging.getLogger("arena.backend.ollama")


class OllamaBackend:
    name = "ollama"

    def __init__(self, base_url: str = "http://localhost:11434", timeout: int = 180):
        self.base = base_url.rstrip("/")
        self.timeout = timeout

    def generate(self, model: str, prompt: str, **opts) -> GenResult:
        images = opts.pop("images", None)
        msg = {"role": "user", "content": prompt}
        if images:
            msg["images"] = images
        messages = inject_system([msg])
        return self._chat(model, messages, tools=[], **opts)

    def generate_with_tools(self, model: str, messages: list[dict], tools: list[dict], **opts) -> GenResult:
        return self._chat(model, inject_system(messages, tools), tools=tools, **opts)

    def chat_turn(self, model: str, messages: list[dict], tools: list[dict], **opts) -> ChatTurnResult:
        """One /api/chat turn — used by the agent loop for multi-step tool use."""
        call_timeout = opts.pop("_timeout", None) or self.timeout
        body: dict = {
            "model": model,
            "messages": inject_system(messages, tools),
            "stream": True,
            "options": {
                "temperature": opts.get("temperature", 0.0),
                "num_predict": opts.get("num_predict", 16384),
                "num_ctx": opts.get("num_ctx", 65536),
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
        r = None
        try:
            r = requests.post(f"{self.base}/api/chat", json=body, stream=True, timeout=call_timeout)
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
                    tokens_in = chunk.get("prompt_eval_count", 0)
                    tokens_out = chunk.get("eval_count", 0)
                    finish_reason = "tool_calls" if tool_calls else "stop"
                    break
        except Exception as e:
            return ChatTurnResult(error=str(e), latency_s=round(time.time() - t0, 3))
        finally:
            if r is not None:
                r.close()

        return ChatTurnResult(
            text=strip_thinking(text),
            tool_calls=tool_calls,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_s=round(time.time() - t0, 3),
            time_to_first=round(ttft, 3),
            finish_reason=finish_reason,
        )

    def _chat(self, model: str, messages: list[dict], tools: list[dict], **opts) -> GenResult:
        """Single-shot /api/chat with auto-repair fallback for broken templates."""
        res = self._do_chat(model, messages, tools, **opts)
        
        # AUTO-REPAIR: If model returned nothing but didn't error, 
        # it's likely a template mismatch or system prompt rejection.
        if not res.error and res.tokens_out == 0 and not res.tool_calls:
            log.info(f"[mcp] auto-repair: {model} returned 0 tokens. Retrying with /api/generate...")
            # Fallback 1: Raw generation (ignore template)
            raw_prompt = "\n\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])
            res_raw = self._do_generate(model, raw_prompt, **opts)
            if res_raw.tokens_out > 0:
                return res_raw
            
            # Fallback 2: No system prompt (some tiny models choke on instructions)
            if any(m["role"] == "system" for m in messages):
                log.info(f"[mcp] auto-repair: Retrying {model} without system prompt...")
                pure_user = [m for m in messages if m["role"] != "system"]
                return self._do_chat(model, pure_user, tools, **opts)

        return res

    def _do_chat(self, model: str, messages: list[dict], tools: list[dict], **opts) -> GenResult:
        """Internal executor for /api/chat."""
        call_timeout = opts.pop("_timeout", None) or self.timeout
        body: dict = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": opts.get("temperature", 0.0),
                "num_predict": opts.get("num_predict", 16384),
                "num_ctx": opts.get("num_ctx", 65536),
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
        r = None
        try:
            r = requests.post(f"{self.base}/api/chat", json=body, stream=True, timeout=call_timeout)
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
                    tokens_in = chunk.get("prompt_eval_count", 0)
                    tokens_out = chunk.get("eval_count", 0)
                    break
        except Exception as e:
            return GenResult(text="", model=model, error=str(e),
                             latency_s=round(time.time() - t0, 3))
        finally:
            if r is not None:
                r.close()

        latency = time.time() - t0
        clean = strip_thinking(text)
        tps = tokens_out / latency if latency > 0 else 0.0
        return GenResult(
            text=clean, model=model,
            tokens_in=tokens_in, tokens_out=tokens_out,
            latency_s=round(latency, 3), tps=round(tps, 1),
            time_to_first=round(ttft, 3),
            tool_calls=tool_calls,
        )

    def _do_generate(self, model: str, prompt: str, **opts) -> GenResult:
        """Internal executor for /api/generate (raw mode)."""
        call_timeout = opts.pop("_timeout", None) or self.timeout
        body: dict = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": opts.get("temperature", 0.0),
                "num_predict": opts.get("num_predict", 16384),
                "num_ctx": opts.get("num_ctx", 65536),
            },
        }
        t0 = time.time()
        ttft = 0.0
        text = ""
        tokens_in = tokens_out = 0
        first = True
        r = None
        try:
            r = requests.post(f"{self.base}/api/generate", json=body, stream=True, timeout=call_timeout)
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue

                content = chunk.get("response", "")
                if first and content:
                    ttft = time.time() - t0
                    first = False
                text += content
                if chunk.get("done"):
                    tokens_in = chunk.get("prompt_eval_count", 0)
                    tokens_out = chunk.get("eval_count", 0)
                    break
        except Exception as e:
            return GenResult(text="", model=model, error=str(e), latency_s=round(time.time() - t0, 3))
        finally:
            if r is not None:
                r.close()

        latency = time.time() - t0
        clean = strip_thinking(text)
        tps = tokens_out / latency if latency > 0 else 0.0
        return GenResult(
            text=clean, model=model,
            tokens_in=tokens_in, tokens_out=tokens_out,
            latency_s=round(latency, 3), tps=round(tps, 1),
            time_to_first=round(ttft, 3),
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
