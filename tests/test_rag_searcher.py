"""Tests for RAG searcher and tools — no ChromaDB/sentence-transformers required."""
from __future__ import annotations

import unittest.mock as mock
from pathlib import Path

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# CodeSearcher — init and pure formatting paths
# ──────────────────────────────────────────────────────────────────────────────

class TestCodeSearcherInit:
    def test_workspace_dir_stored_as_path(self, tmp_path):
        from ollama_arena.rag.searcher import CodeSearcher
        s = CodeSearcher(workspace_dir=str(tmp_path))
        assert isinstance(s.workspace_dir, Path)

    def test_default_index_path(self, tmp_path):
        from ollama_arena.rag.searcher import CodeSearcher
        s = CodeSearcher(workspace_dir=tmp_path)
        assert ".ollama-arena" in str(s.index_path)

    def test_custom_index_path(self, tmp_path):
        from ollama_arena.rag.searcher import CodeSearcher
        idx = tmp_path / "my_idx"
        s = CodeSearcher(workspace_dir=tmp_path, index_path=str(idx))
        assert s.index_path == idx

    def test_lazy_clients_none(self, tmp_path):
        from ollama_arena.rag.searcher import CodeSearcher
        s = CodeSearcher(workspace_dir=tmp_path)
        assert s._chroma_client is None
        assert s._embedding_model is None

    def test_custom_model_name(self, tmp_path):
        from ollama_arena.rag.searcher import CodeSearcher
        s = CodeSearcher(workspace_dir=tmp_path, model_name="my-custom-model")
        assert s.model_name == "my-custom-model"


class TestSearchWithContextEmpty:
    def test_no_results_returns_no_results_message(self, tmp_path):
        from ollama_arena.rag.searcher import CodeSearcher
        s = CodeSearcher(workspace_dir=tmp_path)
        # Patch search to return empty list
        with mock.patch.object(s, "search", return_value=[]):
            result = s.search_with_context("some query", k=5)
        assert "No results found" in result
        assert "some query" in result

    def test_results_formatted(self, tmp_path):
        from ollama_arena.rag.searcher import CodeSearcher
        s = CodeSearcher(workspace_dir=tmp_path)
        fake_results = [
            {
                "content": "def foo():\n    pass\n    extra",
                "metadata": {"file_path": "utils.py", "chunk_index": 0},
                "distance": 0.1,
                "id": "utils.py_abc_0",
            }
        ]
        with mock.patch.object(s, "search", return_value=fake_results):
            result = s.search_with_context("foo function", k=1, context_lines=2)
        assert "utils.py" in result
        assert "foo function" in result

    def test_find_similar_functions_delegates_to_search(self, tmp_path):
        from ollama_arena.rag.searcher import CodeSearcher
        s = CodeSearcher(workspace_dir=tmp_path)
        with mock.patch.object(s, "search", return_value=[]) as m:
            s.find_similar_functions("my_func", k=3)
        m.assert_called_once()
        call_args = m.call_args
        assert "my_func" in call_args[0][0]
        assert call_args[1]["k"] == 3

    def test_find_related_files_delegates_to_search(self, tmp_path):
        from ollama_arena.rag.searcher import CodeSearcher
        s = CodeSearcher(workspace_dir=tmp_path)
        with mock.patch.object(s, "search", return_value=[]) as m:
            s.find_related_files("src/auth.py", k=2)
        m.assert_called_once()
        assert m.call_args[1]["k"] == 2


# ──────────────────────────────────────────────────────────────────────────────
# RAG tools — pure function paths (no ChromaDB)
# ──────────────────────────────────────────────────────────────────────────────

class TestRagToolDefs:
    def test_returns_three_tools(self):
        from ollama_arena.rag.tools import tool_defs
        defs = tool_defs()
        assert len(defs) == 3

    def test_tool_names(self):
        from ollama_arena.rag.tools import tool_defs
        names = {d[0] for d in tool_defs()}
        assert "code_index" in names
        assert "code_search" in names
        assert "code_index_stats" in names

    def test_all_tools_safe_tier(self):
        from ollama_arena.rag.tools import tool_defs
        for name, fn, schema, tier in tool_defs():
            assert tier == "safe"

    def test_code_search_schema_has_required_query(self):
        from ollama_arena.rag.tools import tool_defs
        defs = {d[0]: d for d in tool_defs()}
        schema = defs["code_search"][2]
        params = schema["function"]["parameters"]
        assert "query" in params.get("required", [])


class TestCodeSearchTool:
    def test_missing_query_returns_error(self):
        from ollama_arena.rag import tools
        import ollama_arena.rag.tools as rag_tools
        result = rag_tools.code_search({"k": 3})
        assert "Error" in result or "required" in result.lower()

    def test_code_index_stats_no_index_message(self):
        from ollama_arena.rag import tools as rag_tools
        mock_indexer = mock.MagicMock()
        mock_indexer.get_index_stats.return_value = {"collection": "codebase_index", "chunks_indexed": 0}
        with mock.patch.object(rag_tools, "_get_indexer", return_value=mock_indexer):
            result = rag_tools.code_index_stats({})
        assert "No index" in result or "code_index" in result

    def test_code_index_stats_with_index(self):
        from ollama_arena.rag import tools as rag_tools
        mock_indexer = mock.MagicMock()
        mock_indexer.get_index_stats.return_value = {"collection": "codebase_index", "chunks_indexed": 150}
        with mock.patch.object(rag_tools, "_get_indexer", return_value=mock_indexer):
            result = rag_tools.code_index_stats({})
        assert "150" in result

    def test_code_search_with_mock_searcher(self):
        from ollama_arena.rag import tools as rag_tools
        mock_searcher = mock.MagicMock()
        mock_searcher.search.return_value = [
            {"content": "def foo(): pass", "metadata": {"file_path": "a.py", "chunk_index": 0}, "distance": 0.1}
        ]
        with mock.patch.object(rag_tools, "_get_searcher", return_value=mock_searcher):
            result = rag_tools.code_search({"query": "find foo", "k": 1})
        assert "find foo" in result or "a.py" in result

    def test_code_index_calls_indexer(self):
        from ollama_arena.rag import tools as rag_tools
        mock_indexer = mock.MagicMock()
        mock_indexer.index.return_value = {
            "files_indexed": 5, "skipped_files": 1, "chunks_created": 20, "time_taken": 0.5
        }
        with mock.patch.object(rag_tools, "_get_indexer", return_value=mock_indexer):
            result = rag_tools.code_index({"force": False})
        assert "5" in result
        mock_indexer.index.assert_called_once_with(force=False)

    def test_code_search_perfect_match_shows_similarity(self):
        """distance=0.0 (a perfect match) is falsy in Python, so
        `if result.get("distance"):` used to silently skip printing the
        Similarity line for the *best possible* match. Must check for
        None explicitly, not truthiness."""
        from ollama_arena.rag import tools as rag_tools
        mock_searcher = mock.MagicMock()
        mock_searcher.search.return_value = [
            {"content": "def foo(): pass", "metadata": {"file_path": "a.py", "chunk_index": 0}, "distance": 0.0}
        ]
        with mock.patch.object(rag_tools, "_get_searcher", return_value=mock_searcher):
            result = rag_tools.code_search({"query": "find foo", "k": 1})
        assert "Similarity: 1.000" in result
