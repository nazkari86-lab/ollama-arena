"""Multi-step agent loop: model ↔ MCP tools until final answer or step limit."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Optional

from .backends.base import Backend, GenResult

log = logging.getLogger("arena.agent_loop")


def _parse_tool_arguments(raw) -> dict:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _assistant_message(content: str, tool_calls: list[dict]) -> dict:
    msg: dict[str, Any] = {"role": "assistant", "content": content or ""}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return msg


async def run_agent_loop(
    backend: Backend,
    model: str,
    instruction: str,
    mcp: Any,
    *,
    max_steps: int = 8,
    images: Optional[list[str]] = None,
    **opts,
) -> GenResult:
    """Run an agentic tool loop against *backend* and *mcp* orchestrator."""
    tools = await mcp.get_all_tools()
    msg = {"role": "user", "content": instruction}
    if images:
        msg["images"] = images
    messages: list[dict] = [msg]
    trace: list[dict] = []
    total_latency = 0.0
    tokens_in = tokens_out = 0
    ttft = 0.0
    last_tool_calls: list[dict] = []

    chat_turn = getattr(backend, "chat_turn", None)
    if not tools or not chat_turn:
        # Backends without per-turn tool API: single-shot fallback.
        res = backend.generate_with_tools(model, messages, tools, **opts)
        return GenResult(
            text=res.text,
            model=res.model,
            tokens_in=res.tokens_in,
            tokens_out=res.tokens_out,
            latency_s=res.latency_s,
            tps=res.tps,
            time_to_first=res.time_to_first,
            finish_reason=res.finish_reason,
            error=res.error,
            tool_calls=getattr(res, "tool_calls", []) or [],
            agent_trace=trace,
            backend_type=getattr(res, "backend_type", ""),
        )

    final_text = ""
    finish_reason = "stop"
    error = ""

    for step in range(1, max_steps + 1):
        turn = chat_turn(model, messages, tools, **opts)
        total_latency += turn.latency_s
        tokens_in += turn.tokens_in
        tokens_out += turn.tokens_out
        if step == 1 and turn.time_to_first:
            ttft = turn.time_to_first
        if turn.error:
            error = turn.error
            trace.append({"step": step, "error": turn.error})
            break

        tool_calls = list(turn.tool_calls or [])
        last_tool_calls = tool_calls
        step_record: dict[str, Any] = {
            "step": step,
            "content": turn.text,
            "tool_calls": tool_calls,
            "tool_results": [],
        }

        if tool_calls:
            messages.append(_assistant_message(turn.text, tool_calls))
            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                args = _parse_tool_arguments(fn.get("arguments", ""))
                t0 = time.time()
                try:
                    result = await mcp.execute_tool(name, args)
                except Exception as exc:
                    result = f"Error executing {name}: {exc}"
                    log.warning("[agent_loop] tool %s failed: %s", name, exc)
                tool_lat = round(time.time() - t0, 3)
                step_record["tool_results"].append(
                    {"name": name, "arguments": args, "result": result,
                     "latency_s": tool_lat}
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.get("id") or f"call_{step}_{name}",
                        "content": str(result),
                    }
                )
            trace.append(step_record)
            continue

        final_text = (turn.text or "").strip()
        finish_reason = turn.finish_reason or "stop"
        trace.append(step_record)
        break
    else:
        finish_reason = "max_steps"

    if not final_text and last_tool_calls:
        final_text = json.dumps(last_tool_calls)

    tps = tokens_out / total_latency if total_latency > 0 and tokens_out > 0 else 0.0
    return GenResult(
        text=final_text,
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_s=round(total_latency, 3),
        tps=round(tps, 1),
        time_to_first=round(ttft, 3),
        finish_reason=finish_reason,
        error=error,
        tool_calls=last_tool_calls,
        agent_trace=trace,
        backend_type=getattr(backend, "name", ""),
    )


def run_agent_sync(
    backend: Backend,
    model: str,
    instruction: str,
    mcp: Any,
    *,
    max_steps: int = 8,
    images: Optional[list[str]] = None,
    **opts,
) -> GenResult:
    """Sync wrapper for Arena.run_match (avoids nested event-loop issues)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            run_agent_loop(
                backend, model, instruction, mcp, max_steps=max_steps, images=images, **opts
            )
        )
    # Already inside a running loop (e.g. pytest-asyncio): use a fresh loop in a thread.
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(
            asyncio.run,
            run_agent_loop(
                backend, model, instruction, mcp, max_steps=max_steps, images=images, **opts
            ),
        ).result()
