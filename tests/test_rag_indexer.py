"""Tests for RAG indexer — pure functions only (no ChromaDB required)."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────────────────────────────────────

def _indexer(tmp_dir: Path | None = None):
    from ollama_arena.rag.indexer import CodebaseIndexer
    workspace = tmp_dir or Path("/tmp")
    return CodebaseIndexer(workspace_dir=workspace)


# ──────────────────────────────────────────────────────────────────────────────
# CodebaseIndexer.__init__
# ──────────────────────────────────────────────────────────────────────────────

class TestCodebaseIndexerInit:
    def test_workspace_dir_stored_as_path(self, tmp_path):
        from ollama_arena.rag.indexer import CodebaseIndexer
        idx = CodebaseIndexer(workspace_dir=str(tmp_path))
        assert isinstance(idx.workspace_dir, Path)
        assert idx.workspace_dir == tmp_path

    def test_default_index_path(self, tmp_path):
        from ollama_arena.rag.indexer import CodebaseIndexer
        idx = CodebaseIndexer(workspace_dir=tmp_path)
        # Should be under home dir by default
        assert ".ollama-arena" in str(idx.index_path)

    def test_custom_index_path(self, tmp_path):
        from ollama_arena.rag.indexer import CodebaseIndexer
        idx_path = tmp_path / "my_index"
        idx = CodebaseIndexer(workspace_dir=tmp_path, index_path=str(idx_path))
        assert idx.index_path == idx_path

    def test_default_model_name(self, tmp_path):
        from ollama_arena.rag.indexer import CodebaseIndexer
        idx = CodebaseIndexer(workspace_dir=tmp_path)
        assert "MiniLM" in idx.model_name or idx.model_name != ""

    def test_lazy_clients_are_none(self, tmp_path):
        from ollama_arena.rag.indexer import CodebaseIndexer
        idx = CodebaseIndexer(workspace_dir=tmp_path)
        assert idx._chroma_client is None
        assert idx._embedding_model is None


# ──────────────────────────────────────────────────────────────────────────────
# _should_index_file
# ──────────────────────────────────────────────────────────────────────────────

class TestShouldIndexFile:
    def _check(self, path_str: str, tmp_path: Path) -> bool:
        idx = _indexer(tmp_path)
        return idx._should_index_file(Path(path_str))

    def test_py_indexed(self, tmp_path):
        assert self._check("main.py", tmp_path) is True

    def test_js_indexed(self, tmp_path):
        assert self._check("app.js", tmp_path) is True

    def test_ts_indexed(self, tmp_path):
        assert self._check("index.ts", tmp_path) is True

    def test_tsx_indexed(self, tmp_path):
        assert self._check("Component.tsx", tmp_path) is True

    def test_rust_indexed(self, tmp_path):
        assert self._check("main.rs", tmp_path) is True

    def test_go_indexed(self, tmp_path):
        assert self._check("server.go", tmp_path) is True

    def test_java_indexed(self, tmp_path):
        assert self._check("Main.java", tmp_path) is True

    def test_cpp_indexed(self, tmp_path):
        assert self._check("algo.cpp", tmp_path) is True

    def test_c_header_indexed(self, tmp_path):
        assert self._check("util.h", tmp_path) is True

    def test_pyc_not_indexed(self, tmp_path):
        assert self._check("module.pyc", tmp_path) is False

    def test_png_not_indexed(self, tmp_path):
        assert self._check("image.png", tmp_path) is False

    def test_pdf_not_indexed(self, tmp_path):
        assert self._check("doc.pdf", tmp_path) is False

    def test_md_not_indexed(self, tmp_path):
        assert self._check("README.md", tmp_path) is False

    def test_txt_not_indexed(self, tmp_path):
        assert self._check("notes.txt", tmp_path) is False

    def test_zip_not_indexed(self, tmp_path):
        assert self._check("archive.zip", tmp_path) is False

    def test_pycache_dir_skipped(self, tmp_path):
        idx = _indexer(tmp_path)
        p = Path("__pycache__/module.cpython-311.pyc")
        assert idx._should_index_file(p) is False

    def test_git_dir_skipped(self, tmp_path):
        idx = _indexer(tmp_path)
        p = Path(".git/hooks/pre-commit")
        assert idx._should_index_file(p) is False

    def test_venv_dir_skipped(self, tmp_path):
        idx = _indexer(tmp_path)
        p = Path("venv/lib/site.py")
        assert idx._should_index_file(p) is False

    def test_node_modules_skipped(self, tmp_path):
        idx = _indexer(tmp_path)
        p = Path("node_modules/react/index.js")
        assert idx._should_index_file(p) is False

    def test_dot_venv_dir_skipped(self, tmp_path):
        idx = _indexer(tmp_path)
        p = Path(".venv/lib/python3.11/site-packages/foo.py")
        assert idx._should_index_file(p) is False

    def test_idea_dir_skipped(self, tmp_path):
        idx = _indexer(tmp_path)
        p = Path(".idea/workspace.xml")
        assert idx._should_index_file(p) is False


# ──────────────────────────────────────────────────────────────────────────────
# _chunk_code
# ──────────────────────────────────────────────────────────────────────────────

class TestChunkCode:
    def _chunk(self, code: str, max_chunk_size: int = 1000, tmp_path=None) -> list[str]:
        idx = _indexer(tmp_path)
        return idx._chunk_code(code, max_chunk_size=max_chunk_size)

    def test_short_code_single_chunk(self, tmp_path):
        code = "x = 1\ny = 2\n"
        chunks = self._chunk(code, tmp_path=tmp_path)
        assert len(chunks) == 1
        assert "x = 1" in chunks[0]

    def test_empty_string_single_chunk(self, tmp_path):
        chunks = self._chunk("", tmp_path=tmp_path)
        assert len(chunks) == 1

    def test_long_code_split_into_multiple(self, tmp_path):
        line = "x = " + "a" * 200 + "\n"
        code = line * 10
        chunks = self._chunk(code, max_chunk_size=500, tmp_path=tmp_path)
        assert len(chunks) > 1

    def test_chunks_cover_all_content(self, tmp_path):
        lines = [f"line_{i} = {i}" for i in range(50)]
        code = "\n".join(lines)
        chunks = self._chunk(code, max_chunk_size=100, tmp_path=tmp_path)
        full = "\n".join(chunks)
        for i in range(50):
            assert f"line_{i}" in full

    def test_no_empty_trailing_chunk(self, tmp_path):
        code = "x = 1\n"
        chunks = self._chunk(code, tmp_path=tmp_path)
        assert all(c is not None for c in chunks)

    def test_custom_max_chunk_size(self, tmp_path):
        line = "a" * 50 + "\n"
        code = line * 100
        chunks_small = self._chunk(code, max_chunk_size=100, tmp_path=tmp_path)
        chunks_large = self._chunk(code, max_chunk_size=1000, tmp_path=tmp_path)
        assert len(chunks_small) > len(chunks_large)


# ──────────────────────────────────────────────────────────────────────────────
# _extract_context
# ──────────────────────────────────────────────────────────────────────────────

class TestExtractContext:
    def _make_file(self, tmp_path: Path, name: str, content: str) -> Path:
        p = tmp_path / name
        p.write_text(content)
        return p

    def test_file_name_in_context(self, tmp_path):
        idx = _indexer(tmp_path)
        fp = self._make_file(tmp_path, "my_module.py", "x = 1")
        ctx = idx._extract_context(fp, "x = 1", 0)
        assert "my_module.py" in ctx

    def test_function_detected(self, tmp_path):
        code = "def my_function(arg):\n    return arg\n"
        idx = _indexer(tmp_path)
        fp = self._make_file(tmp_path, "utils.py", code)
        ctx = idx._extract_context(fp, code, 0)
        assert "my_function" in ctx

    def test_class_detected(self, tmp_path):
        code = "class MyClass:\n    pass\n"
        idx = _indexer(tmp_path)
        fp = self._make_file(tmp_path, "models.py", code)
        ctx = idx._extract_context(fp, code, 0)
        assert "MyClass" in ctx

    def test_chunk_index_in_context(self, tmp_path):
        idx = _indexer(tmp_path)
        fp = self._make_file(tmp_path, "f.py", "x = 1")
        ctx = idx._extract_context(fp, "x = 1", 3)
        assert "4" in ctx  # chunk_index + 1

    def test_no_class_no_function_plain_code(self, tmp_path):
        code = "x = 1 + 2\ny = x * 3\n"
        idx = _indexer(tmp_path)
        fp = self._make_file(tmp_path, "math.py", code)
        ctx = idx._extract_context(fp, code, 0)
        assert "math.py" in ctx

    def test_multiple_functions(self, tmp_path):
        code = "def foo():\n    pass\ndef bar():\n    pass\n"
        idx = _indexer(tmp_path)
        fp = self._make_file(tmp_path, "fns.py", code)
        ctx = idx._extract_context(fp, code, 0)
        assert "foo" in ctx
        assert "bar" in ctx

    def test_path_included_in_context(self, tmp_path):
        idx = _indexer(tmp_path)
        fp = self._make_file(tmp_path, "sub.py", "x=1")
        ctx = idx._extract_context(fp, "x=1", 0)
        assert "sub.py" in ctx
