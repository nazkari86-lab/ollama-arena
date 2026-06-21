"""Codebase indexer for RAG - turns code into searchable embeddings."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger("arena.rag.indexer")


class CodebaseIndexer:
    """Index code files for semantic search using ChromaDB."""

    def __init__(
        self,
        workspace_dir: Path | str,
        index_path: Path | str | None = None,
        model_name: str = "all-MiniLM-L6-v2",
    ):
        self.workspace_dir = Path(workspace_dir)
        if index_path is None:
            index_path = Path.home() / ".ollama-arena" / "chroma_index"
        self.index_path = Path(index_path)
        self.model_name = model_name
        self._chroma_client = None
        self._embedding_model = None

    def _get_embedding_model(self):
        """Lazy load sentence-transformers model."""
        if self._embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                log.info(f"Loading embedding model: {self.model_name}")
                self._embedding_model = SentenceTransformer(self.model_name)
            except ImportError:
                log.error(
                    "sentence-transformers not installed. "
                    "Install with: pip install 'ollama-arena[rag]'"
                )
                raise
        return self._embedding_model

    def _get_chroma_client(self):
        """Lazy load ChromaDB client with SQLite backend."""
        if self._chroma_client is None:
            try:
                import chromadb
                log.info(f"Initializing ChromaDB at {self.index_path}")
                self.index_path.mkdir(parents=True, exist_ok=True)
                self._chroma_client = chromadb.PersistentClient(path=str(self.index_path))
            except ImportError:
                log.error(
                    "chromadb not installed. "
                    "Install with: pip install 'ollama-arena[rag]'"
                )
                raise
        return self._chroma_client

    def _should_index_file(self, file_path: Path) -> bool:
        """Determine if a file should be indexed."""
        # Skip common non-code files
        skip_extensions = {
            ".pyc", ".pyo", ".pyd", ".so", ".dylib", ".dll", ".exe",
            ".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf",
            ".zip", ".tar", ".gz", ".bz2",
            ".md", ".txt", ".log",
        }
        skip_dirs = {"__pycache__", ".git", ".venv", "venv", "node_modules", ".idea", ".vscode"}

        # Never follow symlinks: a symlinked file inside the workspace can
        # point anywhere on disk (e.g. ~/.ssh/id_rsa renamed to *.py), and
        # relative_to() succeeds on the symlink's own path even though the
        # *content* read comes from outside workspace_dir. Skipping symlinks
        # prevents arbitrary files from being read into the persisted index.
        if file_path.is_symlink():
            return False

        if file_path.suffix in skip_extensions:
            return False
        if any(part in skip_dirs for part in file_path.parts):
            return False

        # Index source code files
        index_extensions = {".py", ".js", ".ts", ".tsx", ".jsx", ".rs", ".go", ".java", ".cpp", ".h", ".c"}
        return file_path.suffix in index_extensions

    def _chunk_code(self, code: str, max_chunk_size: int = 1000) -> list[str]:
        """Split code into manageable chunks."""
        lines = code.split("\n")
        chunks = []
        current_chunk = []
        current_size = 0

        for line in lines:
            current_chunk.append(line)
            current_size += len(line)
            if current_size >= max_chunk_size:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_size = 0

        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return chunks

    def _extract_context(self, file_path: Path, chunk: str, chunk_index: int) -> str:
        """Extract context metadata for a code chunk."""
        lines = chunk.split("\n")
        # Extract function/class names if available
        functions = []
        classes = []
        for line in lines[:10]:  # Check first 10 lines for definitions
            if line.strip().startswith("def "):
                func_name = line.strip().replace("def ", "").split("(")[0].strip()
                functions.append(func_name)
            elif line.strip().startswith("class "):
                class_name = line.strip().replace("class ", "").split(":")[0].strip()
                classes.append(class_name)

        context = f"File: {file_path.name}\n"
        if classes:
            context += f"Classes: {', '.join(classes)}\n"
        if functions:
            context += f"Functions: {', '.join(functions)}\n"
        context += f"Path: {file_path.relative_to(self.workspace_dir)}\n"
        context += f"Chunk: {chunk_index + 1}"

        return context

    def index(self, force: bool = False) -> dict:
        """Index the workspace codebase.
        
        Returns:
            dict: Indexing statistics (files_indexed, chunks_created, time_taken)
        """
        import time

        start_time = time.time()

        client = self._get_chroma_client()
        collection_name = "codebase_index"

        # Get or create collection
        try:
            collection = client.get_collection(name=collection_name)
            if force:
                client.delete_collection(name=collection_name)
                collection = client.create_collection(name=collection_name)
                log.info("Force reindex: cleared existing collection")
        except Exception as e:
            log.info(f"No existing collection found ({e}); creating new collection")
            collection = client.create_collection(name=collection_name)
            log.info("Created new collection")

        embedding_model = self._get_embedding_model()

        files_indexed = 0
        chunks_created = 0
        skipped_files = 0

        # Find all code files
        code_files = []
        if self.workspace_dir.exists():
            for file_path in self.workspace_dir.rglob("*"):
                if file_path.is_file() and self._should_index_file(file_path):
                    code_files.append(file_path)

        log.info(f"Found {len(code_files)} files to index")

        for file_path in code_files:
            try:
                # Check if file is already indexed
                file_hash = hashlib.md5(file_path.read_bytes()).hexdigest()
                # TODO: Implement incremental indexing by tracking file hashes

                code = file_path.read_text(encoding="utf-8", errors="ignore")
                chunks = self._chunk_code(code)

                for chunk_index, chunk in enumerate(chunks):
                    if not chunk.strip():
                        continue

                    # Create embedding
                    embedding = embedding_model.encode(chunk)

                    # Create document with context
                    document = self._extract_context(file_path, chunk, chunk_index) + "\n\n" + chunk

                    # Add to collection. Use the full relative path (not just
                    # file_path.name) in the id: two different files that
                    # share a basename (e.g. multiple __init__.py) and happen
                    # to have identical content would otherwise collide on
                    # the same id and silently overwrite each other's chunks.
                    relative_path = str(file_path.relative_to(self.workspace_dir))
                    safe_id_prefix = relative_path.replace("/", "_").replace("\\", "_")
                    collection.add(
                        embeddings=[embedding.tolist()],
                        documents=[document],
                        metadatas=[{
                            "file_path": relative_path,
                            "chunk_index": chunk_index,
                            "file_hash": file_hash,
                        }],
                        ids=[f"{safe_id_prefix}_{file_hash}_{chunk_index}"]
                    )
                    chunks_created += 1

                files_indexed += 1
                if files_indexed % 10 == 0:
                    log.info(f"Indexed {files_indexed}/{len(code_files)} files...")

            except Exception as e:
                log.warning(f"Failed to index {file_path}: {e}")
                skipped_files += 1

        time_taken = time.time() - start_time

        stats = {
            "files_indexed": files_indexed,
            "skipped_files": skipped_files,
            "chunks_created": chunks_created,
            "time_taken": time_taken,
        }

        log.info(f"Indexing complete: {stats}")
        return stats

    def get_index_stats(self) -> dict:
        """Get statistics about the current index."""
        client = self._get_chroma_client()
        try:
            collection = client.get_collection(name="codebase_index")
            count = collection.count()
            return {"collection": "codebase_index", "chunks_indexed": count}
        except Exception as e:
            log.info(f"No index collection found: {e}")
            return {"collection": "codebase_index", "chunks_indexed": 0}
