"""Tests for thread binding lifecycle and TTL sweep."""

from __future__ import annotations

import asyncio
import time

import pytest

from pyclaw.channels.thread_bindings_policy import (
    ThreadBindingConfig,
    ThreadBindingRecord,
    ThreadBindingStore,
    check_expiry,
    resolve_thread_binding_config,
)


class TestCheckExpiry:
    def test_not_expired(self) -> None:
        record = ThreadBindingRecord(thread_id="t1", session_key="s1")
        assert check_expiry(record, idle_hours=24.0) is None

    def test_idle_expired(self) -> None:
        record = ThreadBindingRecord(
            thread_id="t1",
            session_key="s1",
            last_activity_at=time.time() - 25 * 3600,
        )
        assert check_expiry(record, idle_hours=24.0) == "idle-expired"

    def test_max_age_expired(self) -> None:
        record = ThreadBindingRecord(
            thread_id="t1",
            session_key="s1",
            bound_at=time.time() - 49 * 3600,
        )
        assert check_expiry(record, idle_hours=0, max_age_hours=48.0) == "max-age-expired"

    def test_idle_takes_precedence_over_max_age(self) -> None:
        now = time.time()
        record = ThreadBindingRecord(
            thread_id="t1",
            session_key="s1",
            bound_at=now - 100 * 3600,
            last_activity_at=now - 25 * 3600,
        )
        assert check_expiry(record, idle_hours=24.0, max_age_hours=48.0) == "idle-expired"

    def test_disabled_ttl(self) -> None:
        record = ThreadBindingRecord(
            thread_id="t1",
            session_key="s1",
            last_activity_at=time.time() - 1000 * 3600,
            bound_at=time.time() - 1000 * 3600,
        )
        assert check_expiry(record, idle_hours=0, max_age_hours=0) is None


class TestResolveConfig:
    def test_defaults(self) -> None:
        cfg = resolve_thread_binding_config()
        assert cfg.idle_hours == 24.0
        assert cfg.max_age_hours == 0.0

    def test_session_level(self) -> None:
        cfg = resolve_thread_binding_config(
            session_config={"threadBindings": {"idleHours": 12, "maxAgeHours": 48}}
        )
        assert cfg.idle_hours == 12.0
        assert cfg.max_age_hours == 48.0

    def test_channel_overrides_session(self) -> None:
        cfg = resolve_thread_binding_config(
            session_config={"threadBindings": {"idleHours": 12}},
            channel_config={"threadBindings": {"idleHours": 6}},
        )
        assert cfg.idle_hours == 6.0

    def test_account_overrides_all(self) -> None:
        cfg = resolve_thread_binding_config(
            session_config={"threadBindings": {"idleHours": 12}},
            channel_config={"threadBindings": {"idleHours": 6}},
            account_config={"threadBindings": {"idleHours": 1}},
        )
        assert cfg.idle_hours == 1.0

    def test_partial_override(self) -> None:
        cfg = resolve_thread_binding_config(
            session_config={"threadBindings": {"maxAgeHours": 72}},
            account_config={"threadBindings": {"idleHours": 2}},
        )
        assert cfg.idle_hours == 2.0
        assert cfg.max_age_hours == 72.0


class TestThreadBindingStore:
    def test_bind_and_get(self) -> None:
        store = ThreadBindingStore()
        record = store.bind("t1", "s1", channel_id="discord")
        assert record.thread_id == "t1"
        assert record.session_key == "s1"
        assert store.get("t1") is record
        assert store.count == 1

    def test_bind_update(self) -> None:
        store = ThreadBindingStore()
        store.bind("t1", "s1")
        old_record = store.get("t1")
        assert old_record is not None

        store.bind("t1", "s2")
        record = store.get("t1")
        assert record is not None
        assert record.session_key == "s2"
        assert store.count == 1

    def test_unbind(self) -> None:
        store = ThreadBindingStore()
        store.bind("t1", "s1")
        removed = store.unbind("t1")
        assert removed is not None
        assert removed.thread_id == "t1"
        assert store.get("t1") is None
        assert store.count == 0

    def test_unbind_nonexistent(self) -> None:
        store = ThreadBindingStore()
        assert store.unbind("nonexistent") is None

    def test_touch(self) -> None:
        store = ThreadBindingStore()
        store.bind("t1", "s1")
        record = store.get("t1")
        assert record is not None
        old_activity = record.last_activity_at

        import time as _time
        _time.sleep(0.01)
        store.touch("t1")
        assert record.last_activity_at > old_activity

    def test_list_all(self) -> None:
        store = ThreadBindingStore()
        store.bind("t1", "s1")
        store.bind("t2", "s2")
        assert len(store.list_all()) == 2

    @pytest.mark.asyncio
    async def test_sweep_removes_expired(self) -> None:
        config = ThreadBindingConfig(idle_hours=0.001)  # ~3.6 seconds
        store = ThreadBindingStore(config)

        store.bind("t1", "s1")
        record = store.get("t1")
        assert record is not None
        record.last_activity_at = time.time() - 10

        expired = await store.sweep_once()
        assert len(expired) == 1
        assert expired[0][0].thread_id == "t1"
        assert expired[0][1] == "idle-expired"
        assert store.count == 0

    @pytest.mark.asyncio
    async def test_sweep_keeps_active(self) -> None:
        config = ThreadBindingConfig(idle_hours=24.0)
        store = ThreadBindingStore(config)
        store.bind("t1", "s1")

        expired = await store.sweep_once()
        assert len(expired) == 0
        assert store.count == 1

    @pytest.mark.asyncio
    async def test_unbind_callback(self) -> None:
        config = ThreadBindingConfig(idle_hours=0.001)
        store = ThreadBindingStore(config)

        unbound: list[tuple[str, str]] = []

        async def on_unbind(record: ThreadBindingRecord, reason: str) -> None:
            unbound.append((record.thread_id, reason))

        store.set_unbind_callback(on_unbind)
        store.bind("t1", "s1")
        record = store.get("t1")
        assert record is not None
        record.last_activity_at = time.time() - 10

        await store.sweep_once()
        assert len(unbound) == 1
        assert unbound[0] == ("t1", "idle-expired")

    @pytest.mark.asyncio
    async def test_sweep_max_age(self) -> None:
        config = ThreadBindingConfig(idle_hours=0, max_age_hours=0.001)
        store = ThreadBindingStore(config)

        store.bind("t1", "s1")
        record = store.get("t1")
        assert record is not None
        record.bound_at = time.time() - 10

        expired = await store.sweep_once()
        assert len(expired) == 1
        assert expired[0][1] == "max-age-expired"


class TestThreadBindingRecord:
    def test_auto_timestamps(self) -> None:
        before = time.time()
        record = ThreadBindingRecord(thread_id="t1", session_key="s1")
        after = time.time()

        assert before <= record.bound_at <= after
        assert before <= record.last_activity_at <= after

    def test_explicit_timestamps(self) -> None:
        record = ThreadBindingRecord(
            thread_id="t1",
            session_key="s1",
            bound_at=1000.0,
            last_activity_at=2000.0,
        )
        assert record.bound_at == 1000.0
        assert record.last_activity_at == 2000.0

    def test_metadata(self) -> None:
        record = ThreadBindingRecord(
            thread_id="t1",
            session_key="s1",
            metadata={"guild_id": "g1"},
        )
        assert record.metadata["guild_id"] == "g1"
