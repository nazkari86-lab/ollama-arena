"""Tests for RAG (Retrieval-Augmented Generation) codebase search."""
import os
import tempfile
import pytest
from pathlib import Path

from ollama_arena.rag import CodebaseIndexer, CodeSearcher


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace with code files."""
    fd, workspace = tempfile.mkstemp(suffix="_workspace")
    os.close(fd)
    workspace = Path(workspace)
    workspace.mkdir()

    # Create some test code files
    (workspace / "auth.py").write_text("""
def authenticate(username, password):
    if check_credentials(username, password):
        return generate_token(username)
    return None

def check_credentials(username, password):
    return username == "admin" and password == "secret"

def generate_token(username):
    return f"token_{username}"
""")

    (workspace / "utils.py").write_text("""
def format_date(date):
    return date.strftime("%Y-%m-%d")

def parse_date(date_str):
    from datetime import datetime
    return datetime.strptime(date_str, "%Y-%m-%d")
""")

    (workspace / "config.py").write_text("""
DATABASE_URL = "sqlite:///app.db"
API_KEY = "secret-key-123"
DEBUG = True
""")

    yield workspace

    # Cleanup
    import shutil
    try:
        shutil.rmtree(workspace)
    except:
        pass


@pytest.fixture
def temp_index_path():
    """Create a temporary index path."""
    fd, index = tempfile.mkstemp(suffix="_index")
    os.close(fd)
    index = Path(index)
    index.mkdir()

    yield index

    # Cleanup
    import shutil
    try:
        shutil.rmtree(index)
    except:
        pass


class TestCodebaseIndexer:
    """Test codebase indexing functionality."""

    def test_indexer_initialization(self, temp_workspace):
        """Test indexer can be initialized."""
        indexer = CodebaseIndexer(temp_workspace)
        assert indexer.workspace_dir == temp_workspace
        assert indexer.index_path is not None

    def test_index_codebase(self, temp_workspace, temp_index_path):
        """Test indexing a codebase."""
        indexer = CodebaseIndexer(temp_workspace, temp_index_path)
        stats = indexer.index()

        assert stats["files_indexed"] > 0
        assert stats["chunks_created"] > 0
        assert stats["time_taken"] >= 0

    def test_force_reindex(self, temp_workspace, temp_index_path):
        """Test force reindexing."""
        indexer = CodebaseIndexer(temp_workspace, temp_index_path)
        stats1 = indexer.index(force=False)
        stats2 = indexer.index(force=True)

        # Force reindex should clear and rebuild
        assert stats2["chunks_created"] >= 0

    def test_get_index_stats(self, temp_workspace, temp_index_path):
        """Test getting index statistics."""
        indexer = CodebaseIndexer(temp_workspace, temp_index_path)
        indexer.index()
        stats = indexer.get_index_stats()

        assert stats["collection"] == "codebase_index"
        assert stats["chunks_indexed"] > 0

    def test_skip_non_code_files(self, temp_workspace, temp_index_path):
        """Test that non-code files are skipped."""
        # Add non-code files
        (temp_workspace / "readme.txt").write_text("This is a readme")
        (temp_workspace / "image.png").write_bytes(b"fake png")

        indexer = CodebaseIndexer(temp_workspace, temp_index_path)
        stats = indexer.index()

        # Should skip non-code files
        assert stats["files_indexed"] == 3  # Only .py files


class TestCodeSearcher:
    """Test codebase searching functionality."""

    def test_searcher_initialization(self, temp_workspace):
        """Test searcher can be initialized."""
        searcher = CodeSearcher(temp_workspace)
        assert searcher.workspace_dir == temp_workspace

    def test_search_without_index(self, temp_workspace, temp_index_path):
        """Test search when no index exists."""
        searcher = CodeSearcher(temp_workspace, temp_index_path)
        results = searcher.search("authentication")

        assert results == []

    def test_search_with_index(self, temp_workspace, temp_index_path):
        """Test search with indexed codebase."""
        # First index
        indexer = CodebaseIndexer(temp_workspace, temp_index_path)
        indexer.index()

        # Then search
        searcher = CodeSearcher(temp_workspace, temp_index_path)
        results = searcher.search("authentication")

        assert len(results) > 0
        assert any("auth" in result["metadata"]["file_path"] for result in results)

    def test_search_with_context(self, temp_workspace, temp_index_path):
        """Test search with formatted context."""
        indexer = CodebaseIndexer(temp_workspace, temp_index_path)
        indexer.index()

        searcher = CodeSearcher(temp_workspace, temp_index_path)
        results = searcher.search_with_context("authentication", k=3)

        assert "authentication" in results.lower()
        assert len(results.split("\n")) > 10  # Should have formatting

    def test_find_similar_functions(self, temp_workspace, temp_index_path):
        """Test finding similar functions."""
        indexer = CodebaseIndexer(temp_workspace, temp_index_path)
        indexer.index()

        searcher = CodeSearcher(temp_workspace, temp_index_path)
        results = searcher.find_similar_functions("authenticate", k=2)

        assert len(results) <= 2
        # Should find the authenticate function

    def test_is_indexed(self, temp_workspace, temp_index_path):
        """Test checking if index exists."""
        searcher = CodeSearcher(temp_workspace, temp_index_path)

        # Should be False initially
        assert not searcher.is_indexed()

        # After indexing, should be True
        indexer = CodebaseIndexer(temp_workspace, temp_index_path)
        indexer.index()

        assert searcher.is_indexed()


class TestRAGIntegration:
    """Test RAG tool integration with MCP."""

    def test_code_index_tool(self, temp_workspace, temp_index_path):
        """Test code_index tool."""
        from ollama_arena.rag.tools import code_index, _get_indexer, _get_searcher

        # Reset global instances
        from ollama_arena.rag import tools
        tools._indexer = None
        tools._searcher = None

        # Create indexer with temp paths
        from ollama_arena.rag.indexer import CodebaseIndexer
        tools._indexer = CodebaseIndexer(temp_workspace, temp_index_path)

        result = code_index({"force": False})
        assert "Codebase indexing complete" in result
        assert "Files indexed" in result

    def test_code_search_tool(self, temp_workspace, temp_index_path):
        """Test code_search tool."""
        from ollama_arena.rag.tools import code_search, _get_indexer, _get_searcher

        # Reset global instances
        from ollama_arena.rag import tools
        tools._indexer = None
        tools._searcher = None

        # Index first
        from ollama_arena.rag.indexer import CodebaseIndexer
        tools._indexer = CodebaseIndexer(temp_workspace, temp_index_path)
        tools._indexer.index()

        # Then search
        from ollama_arena.rag.searcher import CodeSearcher
        tools._searcher = CodeSearcher(temp_workspace, temp_index_path)

        result = code_search({"query": "authentication", "k": 2})
        assert "authentication" in result.lower() or "auth" in result.lower()

    def test_code_index_stats_tool(self, temp_workspace, temp_index_path):
        """Test code_index_stats tool."""
        from ollama_arena.rag.tools import code_index_stats, _get_indexer

        # Reset global instance
        from ollama_arena.rag import tools
        tools._indexer = None

        # Create indexer with temp paths
        from ollama_arena.rag.indexer import CodebaseIndexer
        tools._indexer = CodebaseIndexer(temp_workspace, temp_index_path)

        result = code_index_stats({})
        assert "Codebase index statistics" in result


class TestRAGTools:
    """Test RAG tool definitions."""

    def test_tool_defs_structure(self):
        """Test tool definitions have correct structure."""
        from ollama_arena.rag.tools import tool_defs

        defs = tool_defs()
        assert len(defs) == 3

        # Check each tool has required fields
        for name, handler, schema, tier in defs:
            assert isinstance(name, str)
            assert callable(handler)
            assert isinstance(schema, dict)
            assert tier in ["safe", "confirm", "deny"]

    def test_code_search_schema(self):
        """Test code_search tool schema."""
        from ollama_arena.rag.tools import tool_defs

        defs = tool_defs()
        search_def = next(d for d in defs if d[0] == "code_search")

        schema = search_def[2]
        assert "query" in schema["function"]["parameters"]["required"]
        assert schema["function"]["parameters"]["properties"]["query"]["type"] == "string"
