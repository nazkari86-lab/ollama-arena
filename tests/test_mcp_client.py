import pytest
from ollama_arena.mcp_client import MCPOrchestrator


@pytest.mark.asyncio
async def test_mcp_orchestrator_exposes_tools():
    orchestrator = MCPOrchestrator()
    tools = await orchestrator.get_all_tools()
    names = {t["function"]["name"] for t in tools}
    assert "google_web_search" in names
    assert "code_interpreter" in names
    assert "wikipedia_search" in names


@pytest.mark.asyncio
async def test_mcp_tool_execution_consult_expert():
    orchestrator = MCPOrchestrator()
    result = await orchestrator.execute_tool("consult_expert", {"topic": "tdd"})
    assert "TDD" in result or "test" in result.lower()

    error_result = await orchestrator.execute_tool("non_existent", {})
    assert "not found" in error_result
