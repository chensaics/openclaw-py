"""Memory store — SQLite-backed persistent memory with keyword + hybrid search.

Stores memory entries (key facts, preferences, context) that the agent
can search and retrieve. Uses FTS5 for keyword search with query expansion,
temporal decay, and MMR diversity re-ranking.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pyclaw.memory.mmr import MMRConfig, apply_mmr_to_results
from pyclaw.memory.query_expansion import expand_query_for_fts
from pyclaw.memory.temporal_decay import TemporalDecayConfig, apply_temporal_decay


@dataclass
class MemoryEntry:
    """A single memory entry."""

    id: int
    content: str
    source: str
    tags: list[str]
    created_at: float
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "content": self.content,
            "source": self.source,
            "tags": self.tags,
            "createdAt": self.created_at,
        }
        if self.metadata:
            d["metadata"] = self.metadata
        return d


class MemoryStore:
    """SQLite-backed memory store with FTS5 full-text search."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def open(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def _create_tables(self) -> None:
        assert self._conn
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '[]',
                metadata TEXT,
                created_at REAL NOT NULL
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                content,
                source,
                tags,
                content=memories,
                content_rowid=id
            );

            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, content, source, tags)
                VALUES (new.id, new.content, new.source, new.tags);
            END;

            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, content, source, tags)
                VALUES ('delete', old.id, old.content, old.source, old.tags);
            END;

            CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, content, source, tags)
                VALUES ('delete', old.id, old.content, old.source, old.tags);
                INSERT INTO memories_fts(rowid, content, source, tags)
                VALUES (new.id, new.content, new.source, new.tags);
            END;
        """)

    def add(
        self,
        content: str,
        *,
        source: str = "",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        """Add a new memory entry."""
        assert self._conn
        tags_list = tags or []
        now = time.time()

        cursor = self._conn.execute(
            "INSERT INTO memories (content, source, tags, metadata, created_at) VALUES (?, ?, ?, ?, ?)",
            (content, source, json.dumps(tags_list), json.dumps(metadata) if metadata else None, now),
        )
        self._conn.commit()

        return MemoryEntry(
            id=cursor.lastrowid or 0,
            content=content,
            source=source,
            tags=tags_list,
            created_at=now,
            metadata=metadata,
        )

    def search(self, query: str, *, limit: int = 10) -> list[MemoryEntry]:
        """Search memories using FTS5 full-text search."""
        assert self._conn
        rows = self._conn.execute(
            "SELECT m.id, m.content, m.source, m.tags, m.metadata, m.created_at "
            "FROM memories_fts f "
            "JOIN memories m ON f.rowid = m.id "
            "WHERE memories_fts MATCH ? "
            "ORDER BY rank "
            "LIMIT ?",
            (query, limit),
        ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def search_expanded(
        self,
        query: str,
        *,
        limit: int = 10,
        temporal_decay: TemporalDecayConfig | None = None,
        mmr: MMRConfig | None = None,
        workspace_dir: str | None = None,
    ) -> list[MemoryEntry]:
        """Search with query expansion, temporal decay, and MMR.

        Falls back to raw FTS if expansion produces no keywords.
        """
        assert self._conn

        expanded = expand_query_for_fts(query)
        fts_query = expanded or query

        # Fetch more than limit so decay/MMR can re-rank effectively
        fetch_limit = limit * 3
        try:
            rows = self._conn.execute(
                "SELECT m.id, m.content, m.source, m.tags, m.metadata, m.created_at, rank "
                "FROM memories_fts f "
                "JOIN memories m ON f.rowid = m.id "
                "WHERE memories_fts MATCH ? "
                "ORDER BY rank "
                "LIMIT ?",
                (fts_query, fetch_limit),
            ).fetchall()
        except sqlite3.OperationalError:
            # If expanded query is invalid FTS5, fall back to raw
            rows = self._conn.execute(
                "SELECT m.id, m.content, m.source, m.tags, m.metadata, m.created_at, rank "
                "FROM memories_fts f "
                "JOIN memories m ON f.rowid = m.id "
                "WHERE memories_fts MATCH ? "
                "ORDER BY rank "
                "LIMIT ?",
                (query, fetch_limit),
            ).fetchall()

        if not rows:
            return []

        # Build dicts for decay/MMR pipeline
        items: list[dict[str, Any]] = []
        entries_by_id: dict[int, MemoryEntry] = {}
        for row in rows:
            entry = self._row_to_entry(row)
            entries_by_id[entry.id] = entry
            items.append(
                {
                    "id": str(entry.id),
                    "content": entry.content,
                    "score": 1.0 / (1.0 + max(0.0, row.get("rank", 0.0))),
                    "path": entry.source,
                    "source": entry.source,
                    "snippet": entry.content[:200],
                }
            )

        # Apply temporal decay
        if temporal_decay and temporal_decay.enabled:
            items = apply_temporal_decay(items, config=temporal_decay, workspace_dir=workspace_dir)

        # Sort by score
        items.sort(key=lambda x: x.get("score", 0.0), reverse=True)

        # Apply MMR
        if mmr and mmr.enabled:
            items = apply_mmr_to_results(items, config=mmr)

        # Map back to MemoryEntry
        result: list[MemoryEntry] = []
        for item in items[:limit]:
            eid = int(item["id"])
            if eid in entries_by_id:
                result.append(entries_by_id[eid])
        return result

    def list_recent(self, *, limit: int = 20) -> list[MemoryEntry]:
        """List the most recent memories."""
        assert self._conn
        rows = self._conn.execute(
            "SELECT id, content, source, tags, metadata, created_at FROM memories ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def get(self, memory_id: int) -> MemoryEntry | None:
        """Get a memory by ID."""
        assert self._conn
        row = self._conn.execute(
            "SELECT id, content, source, tags, metadata, created_at FROM memories WHERE id = ?",
            (memory_id,),
        ).fetchone()
        return self._row_to_entry(row) if row else None

    def delete(self, memory_id: int) -> bool:
        """Delete a memory by ID."""
        assert self._conn
        cursor = self._conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def count(self) -> int:
        """Return the total number of memories."""
        assert self._conn
        row = self._conn.execute("SELECT COUNT(*) FROM memories").fetchone()
        return row[0] if row else 0

    @staticmethod
    def _row_to_entry(row: Any) -> MemoryEntry:
        tags_raw = row["tags"]
        try:
            tags = json.loads(tags_raw) if tags_raw else []
        except json.JSONDecodeError:
            tags = []

        metadata_raw = row["metadata"]
        try:
            metadata = json.loads(metadata_raw) if metadata_raw else None
        except json.JSONDecodeError:
            metadata = None

        return MemoryEntry(
            id=row["id"],
            content=row["content"],
            source=row["source"],
            tags=tags,
            created_at=row["created_at"],
            metadata=metadata,
        )

    def __enter__(self) -> MemoryStore:
        self.open()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
