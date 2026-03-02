"""Tests for memory store — SQLite + FTS5."""

from pathlib import Path

import pytest

from pyclaw.memory.store import MemoryStore


@pytest.fixture
def store(tmp_path: Path):
    db_path = tmp_path / "memory.db"
    s = MemoryStore(db_path)
    s.open()
    yield s
    s.close()


def test_add_and_get(store: MemoryStore):
    entry = store.add("The user prefers dark mode", source="chat", tags=["preference"])
    assert entry.id > 0
    assert entry.content == "The user prefers dark mode"
    assert entry.tags == ["preference"]

    fetched = store.get(entry.id)
    assert fetched is not None
    assert fetched.content == entry.content


def test_search(store: MemoryStore):
    store.add("Python is a programming language", source="fact")
    store.add("The user likes coffee", source="preference")
    store.add("TypeScript is also a language", source="fact")

    results = store.search("programming language")
    assert len(results) >= 1
    assert any("programming" in r.content.lower() for r in results)


def test_list_recent(store: MemoryStore):
    for i in range(5):
        store.add(f"Memory {i}", source="test")

    recent = store.list_recent(limit=3)
    assert len(recent) == 3
    # Most recent first
    assert "Memory 4" in recent[0].content


def test_delete(store: MemoryStore):
    entry = store.add("To be deleted", source="test")
    assert store.count() == 1

    deleted = store.delete(entry.id)
    assert deleted is True
    assert store.count() == 0
    assert store.get(entry.id) is None


def test_delete_nonexistent(store: MemoryStore):
    assert store.delete(9999) is False


def test_count(store: MemoryStore):
    assert store.count() == 0
    store.add("One", source="test")
    store.add("Two", source="test")
    assert store.count() == 2


def test_context_manager(tmp_path: Path):
    db_path = tmp_path / "ctx.db"
    with MemoryStore(db_path) as store:
        store.add("Context manager test", source="test")
        assert store.count() == 1


def test_metadata(store: MemoryStore):
    entry = store.add(
        "Important fact",
        source="agent",
        metadata={"confidence": 0.9, "session": "abc123"},
    )
    fetched = store.get(entry.id)
    assert fetched is not None
    assert fetched.metadata is not None
    assert fetched.metadata["confidence"] == 0.9


def test_to_dict(store: MemoryStore):
    entry = store.add("Test entry", source="test", tags=["a", "b"])
    d = entry.to_dict()
    assert d["content"] == "Test entry"
    assert d["tags"] == ["a", "b"]
    assert "createdAt" in d
