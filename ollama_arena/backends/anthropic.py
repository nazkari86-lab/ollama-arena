"""Native Anthropic Messages API backend.

Anthropic's API differs enough from OpenAI (/v1/messages vs /v1/chat/completions,
`x-api-key` header, different SSE event types) that the OpenAI-compat shim
breaks on streaming. This backend speaks the native protocol.

Usage
-----
    from ollama_arena import Arena
    arena = Arena(backend="anthropic", api_key="sk-ant-...")

    # or via env var:
    # ANTHROPIC_API_KEY=sk-ant-... arena benchmark claude-3-5-sonnet-20241022

Supported models (non-exhaustive):
    claude-opus-4-7, claude-sonnet-4-6, claude-haiku-4-5-20251001
    claude-3-5-sonnet-20241022, claude-3-5-haiku-20241022, claude-3-opus-20240229
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Iterator, cast

import requests

from .base import GenResult, ChatTurnResult, strip_thinking, inject_system

log = logging.getLogger("arena.backend.anthropic")

_BASE = "https://api.anthropic.com/v1"
_VERSION = "2023-06-01"
_DEFAULT_MAX_TOKENS = 8192

# Models that support extended thinking (budget tokens) — opt-in via opts
_THINKING_MODELS = {
    "claude-opus-4-7", "claude-sonnet-4-6",
    "claude-3-7-sonnet-20250219",
}


def _messages_to_anthropic(messages: list[dict]) -> tuple[str | None, list[dict]]:
    """Split system prompt from conversation turns and convert to Anthropic format.

    Anthropic's Messages API only accepts role "user"/"assistant" — tool
    round-trips use content blocks, not OpenAI's "tool" role or top-level
    "tool_calls" key. Agent loops (see agent_loop.py) build messages in the
    OpenAI shape regardless of backend, so this conversion has to translate:
      - assistant message with msg["tool_calls"]  -> assistant content
        blocks of type "tool_use"
      - {"role": "tool", "tool_call_id": ..., "content": ...} -> a user
        message with a "tool_result" content block
    Without this, multi-turn agent runs against the Anthropic backend send
    malformed messages on the second turn onward and the API rejects them.
    """
    system: str | None = None
    turns: list[dict] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        images = msg.get("images")
        if role == "system":
            system = content
            continue
        if role == "tool":
            turns.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": msg.get("tool_call_id", ""),
                    "content": str(content),
                }],
            })
            continue
        if role == "assistant" and msg.get("tool_calls"):
            parts: list[dict] = []
            if content:
                parts.append({"type": "text", "text": content})
            for tc in msg["tool_calls"]:
                fn = tc.get("function", {})
                raw_args = fn.get("arguments", "{}")
                if isinstance(raw_args, str):
                    try:
                        raw_args = json.loads(raw_args) if raw_args else {}
                    except json.JSONDecodeError:
                        raw_args = {}
                parts.append({
                    "type": "tool_use",
                    "id": tc.get("id", ""),
                    "name": fn.get("name", ""),
                    "input": raw_args,
                })
            turns.append({"role": "assistant", "content": parts})
            continue
        if images:
            parts = []
            if content:
                parts.append({"type": "text", "text": content})
            for img in images:
                if img.startswith("data:"):
                    media_type, data = img.split(";base64,", 1)
                    media_type = media_type.replace("data:", "")
                else:
                    media_type, data = "image/jpeg", img
                parts.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": data},
                })
            turns.append({"role": "user", "content": parts})
        else:
            turns.append({"role": role, "content": content})
    return system, turns


class AnthropicBackend:
    name = "anthropic"

    def __init__(
        self,
        api_key: str | None = None,
        timeout: int = 180,
        base_url: str = _BASE,
    ):
        self.api_key = (
            api_key
            or os.environ.get("ANTHROPIC_API_KEY")
            or ""
        )
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self._headers = {
            "x-api-key": self.api_key,
            "anthropic-version": _VERSION,
            "content-type": "application/json",
        }

    def _build_body(self, model: str, messages: list[dict], tools: list[dict], **opts) -> dict:
        system, turns = _messages_to_anthropic(inject_system(messages, tools))
        body: dict = {
            "model": model,
            "messages": turns,
            "max_tokens": opts.get("num_predict", opts.get("max_tokens", _DEFAULT_MAX_TOKENS)),
            "temperature": opts.get("temperature", 1.0),
            "stream": True,
        }
        if system:
            body["system"] = system
        if tools:
            body["tools"] = [
                {
                    "name": t["function"]["name"],
                    "description": t["function"].get("description", ""),
                    "input_schema": t["function"].get("parameters", {"type": "object", "properties": {}}),
                }
                for t in tools
            ]
        # Extended thinking budget (opt-in via opts["thinking_budget"])
        if model in _THINKING_MODELS and opts.get("thinking_budget"):
            body["thinking"] = {
                "type": "enabled",
                "budget_tokens": int(opts["thinking_budget"]),
            }
            body.pop("temperature", None)  # incompatible with extended thinking
        return body

    def chat_turn(
        self, model: str, messages: list[dict], tools: list[dict], **opts
    ) -> ChatTurnResult:
        body = self._build_body(model, messages, tools, **opts)
        t0 = time.time()
        ttft = 0.0
        text = ""
        first = True
        tokens_in = tokens_out = 0
        tool_calls: list[dict] = []
        current_tool: dict = {}
        finish_reason = "end_turn"

        r = None
        try:
            r = requests.post(
                f"{self.base}/messages",
                json=body,
                headers=self._headers,
                stream=True,
                timeout=self.timeout,
            )
            if r.status_code != 200:
                return ChatTurnResult(
                    error=f"HTTP {r.status_code}: {r.text[:500]}",
                    latency_s=round(time.time() - t0, 3),
                )

            # requests' stub doesn't model decode_unicode=True returning str
            for raw_line in cast(Iterator[str], r.iter_lines(decode_unicode=True)):
                if not raw_line:
                    continue
                if raw_line.startswith("data:"):
                    data = raw_line[5:].strip()
                    if not data or data == "[DONE]":
                        continue
                    try:
                        ev = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    etype = ev.get("type", "")

                    if etype == "message_start":
                        usage = ev.get("message", {}).get("usage", {})
                        tokens_in = usage.get("input_tokens", tokens_in)

                    elif etype == "content_block_start":
                        block = ev.get("content_block", {})
                        if block.get("type") == "tool_use":
                            current_tool = {
                                "id": block.get("id", ""),
                                "type": "function",
                                "function": {"name": block.get("name", ""), "arguments": ""},
                            }

                    elif etype == "content_block_delta":
                        delta = ev.get("delta", {})
                        dtype = delta.get("type", "")
                        if dtype == "text_delta":
                            piece = delta.get("text", "")
                            if first and piece:
                                ttft = time.time() - t0
                                first = False
                            text += piece
                        elif dtype == "input_json_delta":
                            current_tool.setdefault("function", {})
                            current_tool["function"]["arguments"] = (
                                current_tool["function"].get("arguments", "")
                                + delta.get("partial_json", "")
                            )

                    elif etype == "content_block_stop":
                        if current_tool:
                            tool_calls.append(current_tool)
                            current_tool = {}

                    elif etype == "message_delta":
                        usage = ev.get("usage", {})
                        tokens_out = usage.get("output_tokens", tokens_out)
                        finish_reason = ev.get("delta", {}).get("stop_reason", finish_reason)

            latency = time.time() - t0
            text = strip_thinking(text)
            return ChatTurnResult(
                text=text,
                tool_calls=tool_calls,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_s=round(latency, 3),
                time_to_first=round(ttft, 3),
                finish_reason=finish_reason,
            )
        except Exception as e:
            return ChatTurnResult(
                error=str(e), latency_s=round(time.time() - t0, 3),
            )
        finally:
            if r is not None:
                r.close()

    def generate(self, model: str, prompt: str, **opts) -> GenResult:
        images = opts.pop("images", None)
        msg: dict = {"role": "user", "content": prompt}
        if images:
            msg["images"] = images
        return self.generate_with_tools(model, [msg], tools=[], **opts)

    def generate_with_tools(
        self, model: str, messages: list[dict], tools: list[dict], **opts
    ) -> GenResult:
        turn = self.chat_turn(model, messages, tools, **opts)
        if turn.error:
            return GenResult(
                text="", model=model, error=turn.error, latency_s=turn.latency_s,
            )
        text = turn.text
        if turn.tool_calls and not text:
            text = json.dumps(turn.tool_calls)
        tps = (
            turn.tokens_out / turn.latency_s
            if turn.latency_s > 0 and turn.tokens_out > 0
            else 0.0
        )
        return GenResult(
            text=text,
            model=model,
            tokens_in=turn.tokens_in,
            tokens_out=turn.tokens_out,
            latency_s=turn.latency_s,
            tps=round(tps, 1),
            time_to_first=turn.time_to_first,
            finish_reason=turn.finish_reason,
            tool_calls=turn.tool_calls,
            backend_type=self.name,
        )

    def list_models(self) -> list[str]:
        """Return known Claude models (Anthropic's /models endpoint is restricted)."""
        return [
            "claude-opus-4-7",
            "claude-sonnet-4-6",
            "claude-haiku-4-5-20251001",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
        ]

    def is_alive(self) -> bool:
        return bool(self.api_key)
