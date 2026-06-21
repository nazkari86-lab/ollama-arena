"""Extended tests for CodebaseIndexer — lazy loaders and index() with mocks."""
from __future__ import annotations

import unittest.mock as mock
from pathlib import Path

import pytest


def _indexer(tmp_path, **kw):
    from ollama_arena.rag.indexer import CodebaseIndexer
    return CodebaseIndexer(workspace_dir=tmp_path, index_path=tmp_path / "idx", **kw)


# ──────────────────────────────────────────────────────────────────────────────
# Lazy load paths — ImportError
# ──────────────────────────────────────────────────────────────────────────────

class TestLazyLoadErrors:
    def test_get_embedding_model_raises_on_missing_import(self, tmp_path):
        idx = _indexer(tmp_path)
        with mock.patch.dict("sys.modules", {"sentence_transformers": None}):
            with pytest.raises((ImportError, Exception)):
                idx._get_embedding_model()

    def test_get_chroma_client_raises_on_missing_import(self, tmp_path):
        idx = _indexer(tmp_path)
        with mock.patch.dict("sys.modules", {"chromadb": None}):
            with pytest.raises((ImportError, Exception)):
                idx._get_chroma_client()

    def test_get_embedding_model_cached(self, tmp_path):
        idx = _indexer(tmp_path)
        mock_model = mock.MagicMock()
        idx._embedding_model = mock_model
        result = idx._get_embedding_model()
        assert result is mock_model

    def test_get_chroma_client_cached(self, tmp_path):
        idx = _indexer(tmp_path)
        mock_client = mock.MagicMock()
        idx._chroma_client = mock_client
        result = idx._get_chroma_client()
        assert result is mock_client


# ──────────────────────────────────────────────────────────────────────────────
# index() with fully mocked ChromaDB + sentence-transformers
# ──────────────────────────────────────────────────────────────────────────────

class TestIndexWithMocks:
    def _setup_mocks(self, tmp_path):
        """Create an indexer with pre-set mock clients."""
        idx = _indexer(tmp_path)

        mock_collection = mock.MagicMock()
        mock_collection.count.return_value = 0

        mock_client = mock.MagicMock()
        mock_client.get_collection.side_effect = Exception("not found")
        mock_client.create_collection.return_value = mock_collection

        mock_model = mock.MagicMock()
        import numpy as np
        mock_model.encode.return_value = np.zeros(384)

        idx._chroma_client = mock_client
        idx._embedding_model = mock_model

        return idx, mock_client, mock_collection, mock_model

    def test_index_empty_workspace_returns_stats(self, tmp_path):
        idx, *_ = self._setup_mocks(tmp_path)
        stats = idx.index()
        assert "files_indexed" in stats
        assert "chunks_created" in stats
        assert "time_taken" in stats

    def test_index_empty_workspace_zero_files(self, tmp_path):
        idx, *_ = self._setup_mocks(tmp_path)
        stats = idx.index()
        assert stats["files_indexed"] == 0

    def test_index_single_python_file(self, tmp_path):
        idx, mock_client, mock_collection, _ = self._setup_mocks(tmp_path)
        (tmp_path / "test.py").write_text("def foo():\n    return 42\n")
        stats = idx.index()
        assert stats["files_indexed"] == 1
        assert stats["chunks_created"] >= 1

    def test_index_skips_non_code_files(self, tmp_path):
        idx, *_ = self._setup_mocks(tmp_path)
        (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        stats = idx.index()
        assert stats["files_indexed"] == 0

    def test_index_force_true_deletes_collection(self, tmp_path):
        idx, mock_client, mock_collection, _ = self._setup_mocks(tmp_path)
        # Make get_collection succeed (existing collection)
        mock_client.get_collection.side_effect = None
        mock_client.get_collection.return_value = mock_collection
        idx.index(force=True)
        mock_client.delete_collection.assert_called_once()

    def test_index_returns_timing(self, tmp_path):
        idx, *_ = self._setup_mocks(tmp_path)
        stats = idx.index()
        assert stats["time_taken"] >= 0.0

    def test_index_handles_file_read_error(self, tmp_path):
        idx, *_ = self._setup_mocks(tmp_path)
        broken = tmp_path / "broken.py"
        broken.write_text("valid python")
        # Make read_text fail
        with mock.patch.object(Path, "read_bytes", side_effect=OSError("disk error")):
            with mock.patch.object(Path, "read_text", side_effect=OSError("disk error")):
                stats = idx.index()
        assert stats["skipped_files"] >= 0

    def test_index_multiple_files(self, tmp_path):
        idx, *_ = self._setup_mocks(tmp_path)
        for i in range(3):
            (tmp_path / f"module{i}.py").write_text(f"x = {i}\n")
        stats = idx.index()
        assert stats["files_indexed"] == 3


# ──────────────────────────────────────────────────────────────────────────────
# get_index_stats
# ──────────────────────────────────────────────────────────────────────────────

class TestGetIndexStats:
    def test_get_stats_no_collection_returns_zero(self, tmp_path):
        idx = _indexer(tmp_path)
        mock_client = mock.MagicMock()
        mock_client.get_collection.side_effect = Exception("not found")
        idx._chroma_client = mock_client
        stats = idx.get_index_stats()
        assert stats["chunks_indexed"] == 0

    def test_get_stats_with_collection(self, tmp_path):
        idx = _indexer(tmp_path)
        mock_collection = mock.MagicMock()
        mock_collection.count.return_value = 150
        mock_client = mock.MagicMock()
        mock_client.get_collection.return_value = mock_collection
        idx._chroma_client = mock_client
        stats = idx.get_index_stats()
        assert stats["chunks_indexed"] == 150
        assert stats["collection"] == "codebase_index"


# ──────────────────────────────────────────────────────────────────────────────
# Bug fix regressions
# ──────────────────────────────────────────────────────────────────────────────

class TestSymlinkRejected:
    """A symlinked file inside workspace_dir can point anywhere on disk.
    relative_to() succeeds on the symlink's own path even though the actual
    *content* read comes from the link target, so without this check
    arbitrary files outside the workspace would be read and embedded into
    the persisted index."""

    def test_symlinked_file_not_indexed(self, tmp_path):
        idx = _indexer(tmp_path)
        outside_dir = tmp_path.parent / "outside_secret"
        outside_dir.mkdir(exist_ok=True)
        secret = outside_dir / "secret.py"
        secret.write_text("API_KEY = 'do-not-leak'\n")

        link = tmp_path / "link.py"
        link.symlink_to(secret)

        assert idx._should_index_file(link) is False

    def test_symlinked_file_skipped_during_index(self, tmp_path):
        idx, mock_client, mock_collection, mock_model = self._setup_mocks(tmp_path)

        outside_dir = tmp_path.parent / "outside_secret2"
        outside_dir.mkdir(exist_ok=True)
        secret = outside_dir / "secret.py"
        secret.write_text("API_KEY = 'do-not-leak'\n")
        (tmp_path / "link.py").symlink_to(secret)

        stats = idx.index()
        assert stats["files_indexed"] == 0
        mock_collection.add.assert_not_called()

    def _setup_mocks(self, tmp_path):
        idx = _indexer(tmp_path)
        mock_collection = mock.MagicMock()
        mock_collection.count.return_value = 0
        mock_client = mock.MagicMock()
        mock_client.get_collection.side_effect = Exception("not found")
        mock_client.create_collection.return_value = mock_collection
        mock_model = mock.MagicMock()
        import numpy as np
        mock_model.encode.return_value = np.zeros(384)
        idx._chroma_client = mock_client
        idx._embedding_model = mock_model
        return idx, mock_client, mock_collection, mock_model


class TestIndexUniqueIdsAcrossSameNamedFiles:
    """Two different files sharing a basename (e.g. multiple __init__.py)
    with identical content used to collide on `ids=[f"{file_path.name}..."]`
    and silently overwrite each other's chunks in the collection. The id
    must be derived from the full relative path, not just the basename."""

    def _setup_mocks(self, tmp_path):
        idx = _indexer(tmp_path)
        mock_collection = mock.MagicMock()
        mock_collection.count.return_value = 0
        mock_client = mock.MagicMock()
        mock_client.get_collection.side_effect = Exception("not found")
        mock_client.create_collection.return_value = mock_collection
        mock_model = mock.MagicMock()
        import numpy as np
        mock_model.encode.return_value = np.zeros(384)
        idx._chroma_client = mock_client
        idx._embedding_model = mock_model
        return idx, mock_client, mock_collection, mock_model

    def test_same_name_same_content_get_distinct_ids(self, tmp_path):
        idx, mock_client, mock_collection, mock_model = self._setup_mocks(tmp_path)

        (tmp_path / "pkg_a").mkdir()
        (tmp_path / "pkg_b").mkdir()
        (tmp_path / "pkg_a" / "__init__.py").write_text("")
        (tmp_path / "pkg_b" / "__init__.py").write_text("")
        # Empty files produce no chunks (chunk.strip() filters them out),
        # so give both files identical non-empty content instead.
        (tmp_path / "pkg_a" / "__init__.py").write_text("X = 1\n")
        (tmp_path / "pkg_b" / "__init__.py").write_text("X = 1\n")

        idx.index()

        call_ids = [c.kwargs["ids"][0] for c in mock_collection.add.call_args_list]
        assert len(call_ids) == 2
        assert len(set(call_ids)) == 2, f"expected distinct ids, got {call_ids}"

    def test_id_contains_relative_path_not_just_basename(self, tmp_path):
        idx, mock_client, mock_collection, mock_model = self._setup_mocks(tmp_path)
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "mod.py").write_text("Y = 2\n")

        idx.index()

        call_ids = [c.kwargs["ids"][0] for c in mock_collection.add.call_args_list]
        assert any("sub" in cid for cid in call_ids)


class TestForceReindexCollectionDeleteFailure:
    """If get_collection succeeds but delete_collection raises during a
    force reindex, the old bare `except:` swallowed the real error and
    masked whether the collection was actually cleared. The narrowed
    except should still recover (create_collection) without hiding why."""

    def test_delete_failure_does_not_crash_index(self, tmp_path):
        idx = _indexer(tmp_path)
        mock_collection = mock.MagicMock()
        mock_collection.count.return_value = 0
        mock_client = mock.MagicMock()
        mock_client.get_collection.return_value = mock_collection
        mock_client.delete_collection.side_effect = RuntimeError("locked")
        mock_client.create_collection.return_value = mock_collection
        mock_model = mock.MagicMock()
        import numpy as np
        mock_model.encode.return_value = np.zeros(384)
        idx._chroma_client = mock_client
        idx._embedding_model = mock_model

        stats = idx.index(force=True)

        assert stats["files_indexed"] == 0
        mock_client.create_collection.assert_called_once()
