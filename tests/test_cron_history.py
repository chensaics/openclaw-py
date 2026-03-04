"""Tests for pyclaw.cron.history — execution history store."""

from pathlib import Path

import pytest

from pyclaw.cron.history import ExecutionRecord, ExecutionStatus, HistoryStore


class TestExecutionRecord:
    def test_duration(self) -> None:
        rec = ExecutionRecord(
            id="r1",
            job_id="j1",
            status=ExecutionStatus.COMPLETED,
            started_at=1000.0,
            ended_at=1005.5,
        )
        assert rec.duration_s == pytest.approx(5.5)

    def test_duration_not_started(self) -> None:
        rec = ExecutionRecord(id="r2", job_id="j2")
        assert rec.duration_s == 0.0

    def test_to_dict(self) -> None:
        rec = ExecutionRecord(
            id="r3",
            job_id="j3",
            job_title="Test Job",
            status=ExecutionStatus.FAILED,
            error="timeout",
        )
        d = rec.to_dict()
        assert d["id"] == "r3"
        assert d["status"] == "failed"
        assert d["error"] == "timeout"


class TestHistoryStore:
    def test_add_and_list(self) -> None:
        store = HistoryStore()
        store.add(ExecutionRecord(id="1", job_id="j1", status=ExecutionStatus.COMPLETED))
        store.add(ExecutionRecord(id="2", job_id="j1", status=ExecutionStatus.FAILED))
        store.add(ExecutionRecord(id="3", job_id="j2", status=ExecutionStatus.COMPLETED))

        assert store.count == 3
        recent = store.list_recent(limit=10)
        assert len(recent) == 3

    def test_list_for_job(self) -> None:
        store = HistoryStore()
        store.add(ExecutionRecord(id="1", job_id="j1"))
        store.add(ExecutionRecord(id="2", job_id="j2"))
        store.add(ExecutionRecord(id="3", job_id="j1"))

        j1_records = store.list_for_job("j1")
        assert len(j1_records) == 2

    def test_max_size(self) -> None:
        store = HistoryStore(max_size=3)
        for i in range(5):
            store.add(ExecutionRecord(id=str(i), job_id="j"))
        assert store.count == 3

    def test_update(self) -> None:
        store = HistoryStore()
        store.add(ExecutionRecord(id="u1", job_id="j1", status=ExecutionStatus.RUNNING))
        updated = store.update("u1", status=ExecutionStatus.COMPLETED, output="done")
        assert updated is not None
        assert updated.status == ExecutionStatus.COMPLETED
        assert updated.output == "done"

    def test_get(self) -> None:
        store = HistoryStore()
        store.add(ExecutionRecord(id="g1", job_id="j1", job_title="Get Test"))
        found = store.get("g1")
        assert found is not None
        assert found.job_title == "Get Test"
        assert store.get("nope") is None

    def test_persistence(self, tmp_path: Path) -> None:
        path = tmp_path / "history.json"
        store1 = HistoryStore(persist_path=path)
        store1.add(ExecutionRecord(id="p1", job_id="j1", status=ExecutionStatus.COMPLETED))
        store1.add(ExecutionRecord(id="p2", job_id="j2", status=ExecutionStatus.FAILED, error="oops"))

        store2 = HistoryStore(persist_path=path)
        assert store2.count == 2
        rec = store2.get("p2")
        assert rec is not None
        assert rec.error == "oops"

    def test_clear(self) -> None:
        store = HistoryStore()
        store.add(ExecutionRecord(id="c1", job_id="j1"))
        store.clear()
        assert store.count == 0
