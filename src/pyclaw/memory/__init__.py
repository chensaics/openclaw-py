"""Memory subsystem — SQLite-backed storage with semantic/hybrid search."""

from pyclaw.memory.embeddings import (
    EmbeddingProvider,
    cosine_similarity,
    create_embedding_provider,
    sanitize_and_normalize,
)
from pyclaw.memory.file_manager import (
    MemoryChunk,
    MemoryFileEntry,
    chunk_markdown,
    hash_text,
    list_memory_files,
)
from pyclaw.memory.hybrid import merge_hybrid_results
from pyclaw.memory.mmr import MMRConfig
from pyclaw.memory.query_expansion import expand_query_for_fts, extract_keywords
from pyclaw.memory.store import MemoryStore
from pyclaw.memory.temporal_decay import TemporalDecayConfig

__all__ = [
    "EmbeddingProvider",
    "MMRConfig",
    "MemoryChunk",
    "MemoryFileEntry",
    "MemoryStore",
    "TemporalDecayConfig",
    "chunk_markdown",
    "cosine_similarity",
    "create_embedding_provider",
    "expand_query_for_fts",
    "extract_keywords",
    "hash_text",
    "list_memory_files",
    "merge_hybrid_results",
    "sanitize_and_normalize",
]
