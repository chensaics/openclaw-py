"""QMD store — persistent Q&A memory backed by SQLite + vector search.

Each entry has: question, answer, tags, embedding vector, created/updated
timestamps. Supports semantic search via cosine similarity.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class QmdEntry:
    id: str = ""
    question: str = ""
    answer: str = ""
    tags: list[str] = field(default_factory=list)
    embedding: list[float] = field(default_factory=list)
    created_at: float = 0.0
    updated_at: float = 0.0
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class QmdStore:
    """SQLite-backed Q&A memory store with vector similarity search."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            db_path = Path.home() / ".pyclaw" / "memory" / "qmd.db"
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def open(self) -> None:
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS qmd_entries (
                id TEXT PRIMARY KEY,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                tags TEXT DEFAULT '[]',
                embedding TEXT DEFAULT '[]',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                source TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}'
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_qmd_tags ON qmd_entries(tags)
        """)
        self._conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def add(self, entry: QmdEntry) -> None:
        if not self._conn:
            self.open()
        assert self._conn

        now = time.time()
        if not entry.created_at:
            entry.created_at = now
        entry.updated_at = now
        if not entry.id:
            import uuid
            entry.id = str(uuid.uuid4())

        self._conn.execute(
            """INSERT OR REPLACE INTO qmd_entries
               (id, question, answer, tags, embedding, created_at, updated_at, source, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.id, entry.question, entry.answer,
                json.dumps(entry.tags), json.dumps(entry.embedding),
                entry.created_at, entry.updated_at,
                entry.source, json.dumps(entry.metadata),
            ),
        )
        self._conn.commit()

    def get(self, entry_id: str) -> QmdEntry | None:
        if not self._conn:
            self.open()
        assert self._conn

        row = self._conn.execute(
            "SELECT * FROM qmd_entries WHERE id = ?", (entry_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_entry(row)

    def remove(self, entry_id: str) -> bool:
        if not self._conn:
            self.open()
        assert self._conn
        cur = self._conn.execute("DELETE FROM qmd_entries WHERE id = ?", (entry_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def search_by_tags(self, tags: list[str], limit: int = 20) -> list[QmdEntry]:
        if not self._conn:
            self.open()
        assert self._conn

        all_rows = self._conn.execute(
            "SELECT * FROM qmd_entries ORDER BY updated_at DESC",
        ).fetchall()

        results: list[QmdEntry] = []
        tag_set = set(tags)
        for row in all_rows:
            entry = self._row_to_entry(row)
            if tag_set.intersection(entry.tags):
                results.append(entry)
                if len(results) >= limit:
                    break
        return results

    def search_semantic(
        self, query_embedding: list[float], limit: int = 10, threshold: float = 0.5,
    ) -> list[tuple[QmdEntry, float]]:
        """Search by cosine similarity against stored embeddings."""
        if not self._conn:
            self.open()
        assert self._conn

        all_rows = self._conn.execute(
            "SELECT * FROM qmd_entries WHERE embedding != '[]'",
        ).fetchall()

        scored: list[tuple[QmdEntry, float]] = []
        for row in all_rows:
            entry = self._row_to_entry(row)
            if not entry.embedding:
                continue
            sim = _cosine_similarity(query_embedding, entry.embedding)
            if sim >= threshold:
                scored.append((entry, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    def list_all(self, limit: int = 100) -> list[QmdEntry]:
        if not self._conn:
            self.open()
        assert self._conn
        rows = self._conn.execute(
            "SELECT * FROM qmd_entries ORDER BY updated_at DESC LIMIT ?", (limit,),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def count(self) -> int:
        if not self._conn:
            self.open()
        assert self._conn
        row = self._conn.execute("SELECT COUNT(*) FROM qmd_entries").fetchone()
        return row[0] if row else 0

    @staticmethod
    def _row_to_entry(row: tuple[Any, ...]) -> QmdEntry:
        return QmdEntry(
            id=row[0],
            question=row[1],
            answer=row[2],
            tags=json.loads(row[3]) if row[3] else [],
            embedding=json.loads(row[4]) if row[4] else [],
            created_at=row[5],
            updated_at=row[6],
            source=row[7] if len(row) > 7 else "",
            metadata=json.loads(row[8]) if len(row) > 8 and row[8] else {},
        )


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
