"""Extended tests for CodeSearcher.search() with fully mocked ChromaDB."""
from __future__ import annotations

import unittest.mock as mock

import pytest


def _searcher(tmp_path):
    from ollama_arena.rag.searcher import CodeSearcher
    return CodeSearcher(workspace_dir=tmp_path, index_path=tmp_path / "idx")


class TestCodeSearcherLazyLoad:
    def test_get_embedding_model_cached(self, tmp_path):
        s = _searcher(tmp_path)
        m = mock.MagicMock()
        s._embedding_model = m
        assert s._get_embedding_model() is m

    def test_get_chroma_client_cached(self, tmp_path):
        s = _searcher(tmp_path)
        c = mock.MagicMock()
        s._chroma_client = c
        assert s._get_chroma_client() is c

    def test_get_embedding_model_raises_on_missing(self, tmp_path):
        s = _searcher(tmp_path)
        with mock.patch.dict("sys.modules", {"sentence_transformers": None}):
            with pytest.raises((ImportError, Exception)):
                s._get_embedding_model()

    def test_get_chroma_client_raises_on_missing(self, tmp_path):
        s = _searcher(tmp_path)
        with mock.patch.dict("sys.modules", {"chromadb": None}):
            with pytest.raises((ImportError, Exception)):
                s._get_chroma_client()


class TestCodeSearcherSearch:
    def _mock_searcher(self, tmp_path, collection_results=None):
        s = _searcher(tmp_path)

        mock_model = mock.MagicMock()
        import numpy as np
        mock_model.encode.return_value = np.zeros(384)
        s._embedding_model = mock_model

        mock_collection = mock.MagicMock()
        if collection_results is None:
            mock_collection.query.return_value = {
                "documents": [["def foo(): pass"]],
                "metadatas": [[{"file_path": "foo.py", "chunk_index": 0}]],
                "distances": [[0.1]],
                "ids": [["foo.py_abc_0"]],
            }
        else:
            mock_collection.query.return_value = collection_results

        mock_client = mock.MagicMock()
        mock_client.get_collection.return_value = mock_collection
        s._chroma_client = mock_client

        return s

    def test_search_returns_list(self, tmp_path):
        s = self._mock_searcher(tmp_path)
        result = s.search("find foo function")
        assert isinstance(result, list)

    def test_search_returns_results(self, tmp_path):
        s = self._mock_searcher(tmp_path)
        result = s.search("find foo function", k=1)
        assert len(result) == 1

    def test_search_result_has_content(self, tmp_path):
        s = self._mock_searcher(tmp_path)
        result = s.search("foo")
        assert "content" in result[0]

    def test_search_result_has_metadata(self, tmp_path):
        s = self._mock_searcher(tmp_path)
        result = s.search("foo")
        assert "metadata" in result[0]
        assert result[0]["metadata"]["file_path"] == "foo.py"

    def test_search_result_has_distance(self, tmp_path):
        s = self._mock_searcher(tmp_path)
        result = s.search("foo")
        assert result[0]["distance"] == pytest.approx(0.1)

    def test_search_no_index_returns_empty(self, tmp_path):
        s = _searcher(tmp_path)
        mock_model = mock.MagicMock()
        import numpy as np
        mock_model.encode.return_value = np.zeros(384)
        s._embedding_model = mock_model

        mock_client = mock.MagicMock()
        mock_client.get_collection.side_effect = Exception("no collection")
        s._chroma_client = mock_client

        result = s.search("something")
        assert result == []

    def test_search_empty_documents_returns_empty(self, tmp_path):
        s = self._mock_searcher(tmp_path, collection_results={
            "documents": [[]], "metadatas": [[]], "distances": [[]], "ids": [[]]
        })
        result = s.search("something")
        assert result == []

    def test_search_with_filter_metadata(self, tmp_path):
        s = self._mock_searcher(tmp_path)
        result = s.search("foo", filter_metadata={"file_path": "foo.py"})
        assert isinstance(result, list)


class TestCodeSearcherFindSimilarFunctions:
    def test_returns_list(self, tmp_path):
        s = _searcher(tmp_path)
        with mock.patch.object(s, "search", return_value=[]) as m:
            result = s.find_similar_functions("my_func")
        assert isinstance(result, list)

    def test_passes_function_name_to_search(self, tmp_path):
        s = _searcher(tmp_path)
        with mock.patch.object(s, "search", return_value=[]) as m:
            s.find_similar_functions("calculate_elo", k=5)
        call_query = m.call_args[0][0]
        assert "calculate_elo" in call_query

    def test_passes_k_parameter(self, tmp_path):
        s = _searcher(tmp_path)
        with mock.patch.object(s, "search", return_value=[]) as m:
            s.find_similar_functions("func", k=7)
        assert m.call_args[1]["k"] == 7


class TestCodeSearcherFindRelatedFiles:
    def test_returns_list(self, tmp_path):
        s = _searcher(tmp_path)
        with mock.patch.object(s, "search", return_value=[]):
            result = s.find_related_files("src/auth.py")
        assert isinstance(result, list)

    def test_passes_file_path_to_search(self, tmp_path):
        s = _searcher(tmp_path)
        with mock.patch.object(s, "search", return_value=[]) as m:
            s.find_related_files("src/auth.py", k=3)
        call_query = m.call_args[0][0]
        assert "auth.py" in call_query


class TestSearchWithContextNoneDistance:
    """search() explicitly allows distance to be None (when ChromaDB omits
    'distances' from results), but search_with_context() used to do
    f"{result['distance']:.3f}" unconditionally, which raises TypeError on
    None. Must degrade gracefully instead of crashing."""

    def test_none_distance_does_not_crash(self, tmp_path):
        from ollama_arena.rag.searcher import CodeSearcher
        s = CodeSearcher(workspace_dir=tmp_path)
        fake_results = [
            {
                "content": "def foo(): pass",
                "metadata": {"file_path": "foo.py", "chunk_index": 0},
                "distance": None,
                "id": "foo.py_abc_0",
            }
        ]
        with mock.patch.object(s, "search", return_value=fake_results):
            result = s.search_with_context("foo query", k=1)
        assert "foo.py" in result
        assert "unknown" in result

    def test_numeric_distance_still_formatted(self, tmp_path):
        from ollama_arena.rag.searcher import CodeSearcher
        s = CodeSearcher(workspace_dir=tmp_path)
        fake_results = [
            {
                "content": "def foo(): pass",
                "metadata": {"file_path": "foo.py", "chunk_index": 0},
                "distance": 0.25,
                "id": "foo.py_abc_0",
            }
        ]
        with mock.patch.object(s, "search", return_value=fake_results):
            result = s.search_with_context("foo query", k=1)
        assert "0.250" in result
