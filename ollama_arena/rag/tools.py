"""MCP tool for code search using RAG."""
from __future__ import annotations

import logging
from typing import Callable
from pathlib import Path

from ..rag.indexer import CodebaseIndexer
from ..rag.searcher import CodeSearcher

log = logging.getLogger("arena.rag.tools")


# Lazy-loaded instances
_indexer: CodebaseIndexer | None = None
_searcher: CodeSearcher | None = None


def _get_indexer() -> CodebaseIndexer:
    """Get or create codebase indexer instance."""
    global _indexer
    if _indexer is None:
        workspace_dir = Path.home() / "arena_workspace"
        index_path = Path.home() / ".ollama-arena" / "chroma_index"
        _indexer = CodebaseIndexer(workspace_dir, index_path)
    return _indexer


def _get_searcher() -> CodeSearcher:
    """Get or create code searcher instance."""
    global _searcher
    if _searcher is None:
        workspace_dir = Path.home() / "arena_workspace"
        index_path = Path.home() / ".ollama-arena" / "chroma_index"
        _searcher = CodeSearcher(workspace_dir, index_path)
    return _searcher


def code_index(args: dict) -> str:
    """Index the codebase for semantic search.

    Args:
        args: Dictionary with optional 'force' key to force reindex

    Returns:
        str: Indexing results
    """
    try:
        force = args.get("force", False)
        indexer = _get_indexer()
        stats = indexer.index(force=force)

        return (
            f"Codebase indexing complete!\n"
            f"Files indexed: {stats['files_indexed']}\n"
            f"Skipped files: {stats['skipped_files']}\n"
            f"Chunks created: {stats['chunks_created']}\n"
            f"Time taken: {stats['time_taken']:.2f}s"
        )
    except Exception as e:
        log.exception("Code indexing failed")
        return f"Error indexing codebase: {str(e)}"


def code_search(args: dict) -> str:
    """Search the indexed codebase semantically.

    Args:
        args: Dictionary with:
            - query: Search query (required)
            - k: Number of results (optional, default 5)
            - format: Output format ('simple' or 'detailed', default 'simple')

    Returns:
        str: Search results
    """
    try:
        query = args.get("query")
        if not query:
            return "Error: 'query' parameter is required"

        k = args.get("k", 5)
        format_type = args.get("format", "simple")

        searcher = _get_searcher()

        if format_type == "detailed":
            results = searcher.search_with_context(query, k=k)
        else:
            results_raw = searcher.search(query, k=k)
            results = f"Search results for: {query}\n\n"
            for i, result in enumerate(results_raw, 1):
                metadata = result["metadata"]
                results += f"{i}. {metadata.get('file_path', 'unknown')} (chunk {metadata.get('chunk_index', '?')})\n"
                if result.get("distance") is not None:
                    results += f"   Similarity: {1 - result['distance']:.3f}\n"

        return results

    except Exception as e:
        log.exception("Code search failed")
        return f"Error searching codebase: {str(e)}"


def code_index_stats(args: dict) -> str:
    """Get statistics about the codebase index.

    Args:
        args: Dictionary (unused)

    Returns:
        str: Index statistics
    """
    try:
        indexer = _get_indexer()
        stats = indexer.get_index_stats()

        if stats["chunks_indexed"] == 0:
            return "No index found. Run code_index first."

        return (
            f"Codebase index statistics:\n"
            f"Collection: {stats['collection']}\n"
            f"Chunks indexed: {stats['chunks_indexed']}\n"
            f"Index location: {Path.home() / '.ollama-arena' / 'chroma_index'}"
        )
    except Exception as e:
        log.exception("Failed to get index stats")
        return f"Error getting index stats: {str(e)}"


def tool_defs() -> list[tuple[str, Callable, dict, str]]:
    """Return RAG tool definitions for MCP registry."""
    return [
        (
            "code_index",
            code_index,
            {
                "type": "function",
                "function": {
                    "name": "code_index",
                    "description": "Index the arena_workspace codebase for semantic search. Run this once to enable code search.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "force": {
                                "type": "boolean",
                                "description": "Force reindex even if index exists (clears existing index)",
                            },
                        },
                    },
                },
            },
            "safe",
        ),
        (
            "code_search",
            code_search,
            {
                "type": "function",
                "function": {
                    "name": "code_search",
                    "description": "Search the indexed codebase semantically. Find code by meaning, not just text matching.",
                    "parameters": {
                        "type": "object",
                        "required": ["query"],
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query - can be natural language (e.g., 'find authentication function') or code-like",
                            },
                            "k": {
                                "type": "integer",
                                "description": "Number of results to return (default 5)",
                                "default": 5,
                            },
                            "format": {
                                "type": "string",
                                "enum": ["simple", "detailed"],
                                "description": "Output format (default simple)",
                                "default": "simple",
                            },
                        },
                    },
                },
            },
            "safe",
        ),
        (
            "code_index_stats",
            code_index_stats,
            {
                "type": "function",
                "function": {
                    "name": "code_index_stats",
                    "description": "Get statistics about the codebase index (number of indexed chunks, etc.)",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                    },
                },
            },
            "safe",
        ),
    ]
