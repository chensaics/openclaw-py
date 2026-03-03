"""LanceDB memory backend — vector-native storage with hybrid search.

Optional dependency: ``lancedb`` + ``pyarrow``. If not installed,
``LanceDBBackend`` raises ``ImportError`` at initialization.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, cast

from pyclaw.memory.backend import (
    MemoryBackend,
    MemoryRecord,
    MemorySearchOptions,
    register_memory_backend,
)

logger = logging.getLogger(__name__)

COLLECTION_NAME = "memories"
DEFAULT_EMBEDDING_DIM = 1536


class LanceDBBackend(MemoryBackend):
    """LanceDB-based memory backend with vector search."""

    def __init__(
        self,
        db_path: str = "~/.pyclaw/memory-lance",
        *,
        embedding_dim: int = DEFAULT_EMBEDDING_DIM,
    ) -> None:
        self._db_path = db_path
        self._embedding_dim = embedding_dim
        self._db: Any = None
        self._table: Any = None

    @property
    def name(self) -> str:
        return "lancedb"

    async def initialize(self) -> None:
        try:
            import lancedb as ldb
        except ImportError as exc:
            raise ImportError(
                "lancedb is required for LanceDBBackend. "
                "Install it with: pip install lancedb"
            ) from exc

        self._db = ldb.connect(self._db_path)

        try:
            self._table = self._db.open_table(COLLECTION_NAME)
        except Exception:
            import pyarrow as pa

            schema = pa.schema([
                pa.field("id", pa.string()),
                pa.field("content", pa.string()),
                pa.field("source", pa.string()),
                pa.field("tags", pa.string()),
                pa.field("metadata", pa.string()),
                pa.field("created_at", pa.float64()),
                pa.field("vector", pa.list_(pa.float32(), self._embedding_dim)),
            ])
            self._table = self._db.create_table(COLLECTION_NAME, schema=schema)

        logger.info("LanceDB backend initialized at %s", self._db_path)

    async def close(self) -> None:
        self._table = None
        self._db = None

    async def add(
        self,
        content: str,
        *,
        source: str = "",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        embedding: list[float] | None = None,
    ) -> MemoryRecord:
        if not self._table:
            raise RuntimeError("LanceDB backend not initialized")

        import json

        record_id = str(uuid.uuid4())
        vector = embedding or [0.0] * self._embedding_dim
        now = time.time()

        row = {
            "id": record_id,
            "content": content,
            "source": source,
            "tags": json.dumps(tags or []),
            "metadata": json.dumps(metadata or {}),
            "created_at": now,
            "vector": vector,
        }
        self._table.add([row])

        return MemoryRecord(
            id=record_id,
            content=content,
            source=source,
            tags=tags or [],
            score=1.0,
            created_at=now,
            metadata=metadata or {},
        )

    async def search(
        self,
        query: str,
        *,
        embedding: list[float] | None = None,
        options: MemorySearchOptions | None = None,
    ) -> list[MemoryRecord]:
        if not self._table:
            raise RuntimeError("LanceDB backend not initialized")

        import json

        opts = options or MemorySearchOptions()

        if embedding:
            results = (
                self._table.search(embedding)
                .limit(opts.limit)
                .to_list()
            )
        elif query:
            # Full-text search fallback if available
            try:
                results = (
                    self._table.search(query, query_type="fts")
                    .limit(opts.limit)
                    .to_list()
                )
            except Exception:
                results = self._table.to_pandas().head(opts.limit).to_dict("records")
        else:
            results = self._table.to_pandas().head(opts.limit).to_dict("records")

        records: list[MemoryRecord] = []
        for row in results:
            distance = row.get("_distance", 0.0)
            score = 1.0 / (1.0 + distance) if distance >= 0 else 0.0

            if score < opts.min_score:
                continue

            try:
                tags = json.loads(row.get("tags", "[]"))
            except (json.JSONDecodeError, TypeError):
                tags = []

            try:
                metadata = json.loads(row.get("metadata", "{}"))
            except (json.JSONDecodeError, TypeError):
                metadata = {}

            records.append(MemoryRecord(
                id=row["id"],
                content=row["content"],
                source=row.get("source", ""),
                tags=tags,
                score=score,
                created_at=row.get("created_at", 0.0),
                metadata=metadata,
            ))

        return records

    async def delete(self, record_id: str) -> bool:
        if not self._table:
            raise RuntimeError("LanceDB backend not initialized")

        try:
            self._table.delete(f"id = '{record_id}'")
            return True
        except Exception:
            logger.warning("Failed to delete memory %s from LanceDB", record_id)
            return False

    async def count(self) -> int:
        if not self._table:
            return 0
        return cast(int, self._table.count_rows())

    async def list_recent(self, *, limit: int = 20) -> list[MemoryRecord]:
        if not self._table:
            return []

        import json

        df = self._table.to_pandas().sort_values("created_at", ascending=False).head(limit)
        records: list[MemoryRecord] = []
        for _, row in df.iterrows():
            try:
                tags = json.loads(row.get("tags", "[]"))
            except (json.JSONDecodeError, TypeError):
                tags = []
            try:
                metadata = json.loads(row.get("metadata", "{}"))
            except (json.JSONDecodeError, TypeError):
                metadata = {}

            records.append(MemoryRecord(
                id=row["id"],
                content=row["content"],
                source=row.get("source", ""),
                tags=tags,
                score=1.0,
                created_at=row.get("created_at", 0.0),
                metadata=metadata,
            ))
        return records


# Auto-register
register_memory_backend("lancedb", LanceDBBackend)
