import pytest
from ollama_arena.mcp_client import MCPOrchestrator

@pytest.mark.asyncio
async def test_mcp_orchestrator_loads_tools():
    # Mock config representing the user's requested stack
    config = {
        "sqlite": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-sqlite", "--db", "test.db"]},
        "playwright": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-playwright"]}
    }
    orchestrator = MCPOrchestrator(config)
    tools = await orchestrator.get_all_tools()
    assert len(tools) > 0
    assert any(t["function"]["name"] == "sqlite_query" for t in tools)
    assert any(t["function"]["name"] == "browser_navigate" for t in tools)

@pytest.mark.asyncio
async def test_mcp_tool_execution():
    orchestrator = MCPOrchestrator({"sqlite": {}})
    result = await orchestrator.execute_tool("sqlite_query", {"query": "SELECT * FROM users"})
    assert "Mock DB result" in result
    
    error_result = await orchestrator.execute_tool("non_existent", {})
    assert "not found" in error_result
