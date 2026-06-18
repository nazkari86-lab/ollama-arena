"""MCP web tool handlers — mocked HTTP responses."""
import pytest
from unittest.mock import MagicMock, patch

from ollama_arena.mcp_client import MCPOrchestrator, _real_ddg_search, _real_wikipedia_search


@pytest.fixture
def orch():
    return MCPOrchestrator()


@pytest.mark.asyncio
async def test_ddg_search_mocked(orch):
    html = '<a class="result__a" href="#">First Result</a>'
    mock_resp = MagicMock(ok=True, text=html)
    with patch("ollama_arena.mcp.tools.web.requests.get", return_value=mock_resp):
        out = await orch.execute_tool("ddg_search", {"query": "python asyncio"})
    assert "First Result" in out
    assert "python asyncio" in out


@pytest.mark.asyncio
async def test_google_web_search_alias(orch):
    orch._registry["google_web_search"].handler = lambda _a: "mocked results"
    out = await orch.execute_tool("google_web_search", {"query": "test"})
    assert out == "mocked results"


@pytest.mark.asyncio
async def test_wikipedia_search_mocked(orch):
    orch._registry["wikipedia_search"].handler = lambda _a: (
        "Wikipedia: Python\n\nprogramming language"
    )
    out = await orch.execute_tool("wikipedia_search", {"query": "Python"})
    assert "Python" in out
    assert "programming language" in out


def test_ddg_search_direct_empty_query():
    with patch("ollama_arena.mcp.tools.web.requests.get", side_effect=Exception("offline")):
        out = _real_ddg_search({"query": "test"})
    assert "Error" in out or "No results" in out


def test_wikipedia_empty_query():
    assert "No query" in _real_wikipedia_search({}) or "Error" in _real_wikipedia_search({})


@pytest.mark.asyncio
async def test_web_fetch_mocked(orch):
    mock_resp = MagicMock(ok=True, text="<html><body><p>Hello</p></body></html>")
    with patch("ollama_arena.mcp.tools.web.requests.get", return_value=mock_resp):
        out = await orch.execute_tool("web_fetch", {"url": "https://example.com"})
    assert "Hello" in out
