"""Tests for QMD — CRUD, tag search, semantic search."""

from __future__ import annotations

import os
import tempfile

import pytest

from pyclaw.memory.qmd.store import QmdEntry, QmdStore


class TestQmdStoreCRUD:
    def test_add_and_get(self):
        with tempfile.TemporaryDirectory() as td:
            store = QmdStore(os.path.join(td, "test.db"))
            store.open()
            entry = QmdEntry(question="What is Python?", answer="A language", tags=["lang"])
            store.add(entry)
            assert entry.id != ""

            fetched = store.get(entry.id)
            assert fetched is not None
            assert fetched.question == "What is Python?"
            assert fetched.answer == "A language"
            assert fetched.tags == ["lang"]
            store.close()

    def test_count(self):
        with tempfile.TemporaryDirectory() as td:
            store = QmdStore(os.path.join(td, "test.db"))
            store.open()
            assert store.count() == 0
            store.add(QmdEntry(question="Q1", answer="A1"))
            store.add(QmdEntry(question="Q2", answer="A2"))
            assert store.count() == 2
            store.close()

    def test_remove(self):
        with tempfile.TemporaryDirectory() as td:
            store = QmdStore(os.path.join(td, "test.db"))
            store.open()
            entry = QmdEntry(question="Q", answer="A")
            store.add(entry)
            assert store.count() == 1
            assert store.remove(entry.id) is True
            assert store.count() == 0
            assert store.remove("nonexistent") is False
            store.close()

    def test_list_all(self):
        with tempfile.TemporaryDirectory() as td:
            store = QmdStore(os.path.join(td, "test.db"))
            store.open()
            for i in range(5):
                store.add(QmdEntry(question=f"Q{i}", answer=f"A{i}"))
            all_entries = store.list_all(limit=3)
            assert len(all_entries) == 3
            store.close()

    def test_update_existing(self):
        with tempfile.TemporaryDirectory() as td:
            store = QmdStore(os.path.join(td, "test.db"))
            store.open()
            entry = QmdEntry(id="fixed-id", question="Q", answer="A1")
            store.add(entry)

            updated = QmdEntry(id="fixed-id", question="Q", answer="A2")
            store.add(updated)

            assert store.count() == 1
            fetched = store.get("fixed-id")
            assert fetched is not None
            assert fetched.answer == "A2"
            store.close()


class TestQmdStoreTagSearch:
    def test_search_by_tags(self):
        with tempfile.TemporaryDirectory() as td:
            store = QmdStore(os.path.join(td, "test.db"))
            store.open()
            store.add(QmdEntry(question="Python?", answer="Language", tags=["lang", "python"]))
            store.add(QmdEntry(question="Flet?", answer="Framework", tags=["ui", "python"]))
            store.add(QmdEntry(question="React?", answer="Library", tags=["ui", "js"]))

            results = store.search_by_tags(["python"])
            assert len(results) == 2

            results = store.search_by_tags(["js"])
            assert len(results) == 1
            assert results[0].question == "React?"

            results = store.search_by_tags(["nonexistent"])
            assert len(results) == 0
            store.close()


class TestQmdStoreSemanticSearch:
    def test_cosine_similarity_search(self):
        with tempfile.TemporaryDirectory() as td:
            store = QmdStore(os.path.join(td, "test.db"))
            store.open()
            store.add(QmdEntry(question="Q1", answer="A1", embedding=[1.0, 0.0, 0.0]))
            store.add(QmdEntry(question="Q2", answer="A2", embedding=[0.0, 1.0, 0.0]))
            store.add(QmdEntry(question="Q3", answer="A3", embedding=[0.0, 0.0, 1.0]))

            results = store.search_semantic([1.0, 0.0, 0.0], limit=2, threshold=0.5)
            assert len(results) == 1
            assert results[0][0].answer == "A1"
            assert results[0][1] > 0.99

            results = store.search_semantic([0.7, 0.7, 0.0], limit=5, threshold=0.5)
            assert len(results) == 2
            store.close()

    def test_no_embeddings(self):
        with tempfile.TemporaryDirectory() as td:
            store = QmdStore(os.path.join(td, "test.db"))
            store.open()
            store.add(QmdEntry(question="Q", answer="A"))
            results = store.search_semantic([1.0, 0.0], limit=5, threshold=0.5)
            assert len(results) == 0
            store.close()

    def test_threshold_filtering(self):
        with tempfile.TemporaryDirectory() as td:
            store = QmdStore(os.path.join(td, "test.db"))
            store.open()
            store.add(QmdEntry(question="Q", answer="A", embedding=[1.0, 0.0]))
            results = store.search_semantic([0.0, 1.0], limit=5, threshold=0.9)
            assert len(results) == 0
            store.close()
