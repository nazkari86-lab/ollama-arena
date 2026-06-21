"""Semantic code search using indexed embeddings."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger("arena.rag.searcher")


class CodeSearcher:
    """Search indexed codebase using semantic similarity."""

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
        """Lazy load ChromaDB client."""
        if self._chroma_client is None:
            try:
                import chromadb
                log.info(f"Loading ChromaDB from {self.index_path}")
                self._chroma_client = chromadb.PersistentClient(path=str(self.index_path))
            except ImportError:
                log.error(
                    "chromadb not installed. "
                    "Install with: pip install 'ollama-arena[rag]'"
                )
                raise
        return self._chroma_client

    def search(
        self,
        query: str,
        k: int = 5,
        filter_metadata: Optional[dict] = None,
    ) -> list[dict]:
        """Search the codebase for relevant code chunks.

        Args:
            query: Search query (natural language or code-like)
            k: Number of results to return
            filter_metadata: Optional metadata filters (e.g., {"file_path": "src/"})

        Returns:
            list[dict]: Search results with metadata and content
        """
        embedding_model = self._get_embedding_model()
        client = self._get_chroma_client()

        try:
            collection = client.get_collection(name="codebase_index")
        except Exception as e:
            log.warning(f"No index found ({e}). Run indexer first.")
            return []

        # Create query embedding
        query_embedding = embedding_model.encode(query).tolist()

        # Search
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=filter_metadata,
        )

        if not results["documents"] or not results["documents"][0]:
            log.info(f"No results found for query: {query}")
            return []

        # Format results
        formatted_results = []
        for i in range(len(results["documents"][0])):
            formatted_results.append({
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else None,
                "id": results["ids"][0][i] if results["ids"] else None,
            })

        return formatted_results

    def search_with_context(
        self,
        query: str,
        k: int = 5,
        context_lines: int = 3,
    ) -> str:
        """Search and return formatted results with file context.

        Args:
            query: Search query
            k: Number of results
            context_lines: Lines of context to include

        Returns:
            str: Formatted search results
        """
        results = self.search(query, k=k)

        if not results:
            return f"No results found for: {query}"

        formatted = f"Search results for: {query}\n"
        formatted += "=" * 60 + "\n\n"

        for i, result in enumerate(results, 1):
            metadata = result["metadata"]
            distance = result.get("distance")
            distance_str = f"{distance:.3f}" if distance is not None else "unknown"
            formatted += f"Result {i} (distance: {distance_str})\n"
            formatted += f"File: {metadata.get('file_path', 'unknown')}\n"
            formatted += f"Chunk: {metadata.get('chunk_index', 'unknown')}\n"
            formatted += "-" * 60 + "\n"

            # Show first few lines of content
            content_lines = result["content"].split("\n")
            preview_lines = content_lines[:context_lines]
            formatted += "\n".join(preview_lines)

            if len(content_lines) > context_lines:
                formatted += f"\n... ({len(content_lines) - context_lines} more lines)"

            formatted += "\n\n"

        return formatted

    def find_similar_functions(
        self,
        function_name: str,
        k: int = 5,
    ) -> list[dict]:
        """Find functions similar to the given function name.

        Args:
            function_name: Name of function to find similar to
            k: Number of results

        Returns:
            list[dict]: Similar functions with their code
        """
        # Construct a query that includes the function name
        query = f"function {function_name} implementation code"
        return self.search(query, k=k)

    def find_related_files(
        self,
        file_path: str,
        k: int = 5,
    ) -> list[dict]:
        """Find files related to the given file path.

        Args:
            file_path: Relative path to file
            k: Number of results

        Returns:
            list[dict]: Related files and their code
        """
        # Search for content from the file
        query = f"code from {file_path}"
        return self.search(query, k=k, filter_metadata={"file_path": file_path})

    def is_indexed(self) -> bool:
        """Check if codebase is indexed."""
        client = self._get_chroma_client()
        try:
            collection = client.get_collection(name="codebase_index")
            return collection.count() > 0
        except Exception as e:
            log.info(f"No index found: {e}")
            return False
