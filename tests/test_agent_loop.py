"""Tests for multi-step agent loop."""
import asyncio

import pytest

from ollama_arena.agent_loop import run_agent_loop
from ollama_arena.backends.base import ChatTurnResult
from ollama_arena.mcp_client import MCPOrchestrator


class _ScriptedBackend:
    name = "fake"

    def __init__(self, turns: list[ChatTurnResult]):
        self._turns = list(turns)
        self._i = 0

    def chat_turn(self, model, messages, tools, **opts):
        if self._i >= len(self._turns):
            return ChatTurnResult(text="done", tool_calls=[], finish_reason="stop")
        turn = self._turns[self._i]
        self._i += 1
        return turn


@pytest.mark.asyncio
async def test_agent_loop_multi_step():
    orchestrator = MCPOrchestrator(use_mock=True)
    backend = _ScriptedBackend(
        [
            ChatTurnResult(
                text="",
                tool_calls=[
                    {
                        "id": "c1",
                        "function": {
                            "name": "sqlite_query",
                            "arguments": '{"query": "SELECT * FROM users"}',
                        },
                    }
                ],
                finish_reason="tool_calls",
            ),
            ChatTurnResult(
                text="Found users in the database.",
                tool_calls=[],
                finish_reason="stop",
            ),
        ]
    )

    result = await run_agent_loop(
        backend, "fake-model", "List users", orchestrator, max_steps=4
    )

    assert result.ok
    assert "Found users" in result.text
    assert len(result.agent_trace) == 2
    assert result.agent_trace[0]["tool_calls"][0]["function"]["name"] == "sqlite_query"
    assert result.agent_trace[0]["tool_results"][0]["name"] == "sqlite_query"


@pytest.mark.asyncio
async def test_agent_loop_max_steps():
    orchestrator = MCPOrchestrator(use_mock=True)
    infinite_tools = ChatTurnResult(
        text="",
        tool_calls=[
            {
                "id": "c1",
                "function": {"name": "search_docs", "arguments": "{}"},
            }
        ],
        finish_reason="tool_calls",
    )
    backend = _ScriptedBackend([infinite_tools, infinite_tools, infinite_tools])

    result = await run_agent_loop(
        backend, "fake-model", "Keep searching", orchestrator, max_steps=2
    )

    assert result.finish_reason == "max_steps"
    assert len(result.agent_trace) == 2
