"""Tests for ACP — session store, types."""

from __future__ import annotations

from pyclaw.acp.session import AcpSession, create_in_memory_session_store
from pyclaw.acp.types import AcpAgentInfo, AcpSessionMeta


class TestAcpSessionStore:
    def test_create_and_get(self):
        store = create_in_memory_session_store()
        meta = AcpSessionMeta(session_id="s1", agent_id="main")
        session = store.create_session("s1", meta)
        assert isinstance(session, AcpSession)
        assert store.has_session("s1")
        assert store.get_session("s1") is session

    def test_get_nonexistent(self):
        store = create_in_memory_session_store()
        assert store.get_session("missing") is None
        assert not store.has_session("missing")

    def test_list_sessions(self):
        store = create_in_memory_session_store()
        store.create_session("s1", AcpSessionMeta(session_id="s1"))
        store.create_session("s2", AcpSessionMeta(session_id="s2"))
        assert len(store.list_sessions()) == 2

    def test_remove_session(self):
        store = create_in_memory_session_store()
        store.create_session("s1", AcpSessionMeta(session_id="s1"))
        store.remove_session("s1")
        assert not store.has_session("s1")

    def test_max_sessions_eviction(self):
        store = create_in_memory_session_store(max_sessions=3)
        for i in range(5):
            store.create_session(f"s{i}", AcpSessionMeta(session_id=f"s{i}"))
        assert len(store.list_sessions()) <= 3

    def test_active_run_lifecycle(self):
        store = create_in_memory_session_store()
        store.create_session("s1", AcpSessionMeta(session_id="s1"))

        store.set_active_run("s1", "run-1")
        session = store.get_session("s1")
        assert session is not None
        assert session.active_run_id == "run-1"

        store.clear_active_run("s1")
        session = store.get_session("s1")
        assert session is not None
        assert session.active_run_id is None

    def test_cancel_active_run(self):
        store = create_in_memory_session_store()
        store.create_session("s1", AcpSessionMeta(session_id="s1"))
        store.set_active_run("s1", "run-2")
        run_id = store.cancel_active_run("s1")
        assert run_id == "run-2"
        session = store.get_session("s1")
        assert session is not None
        assert session.active_run_id is None

    def test_cancel_no_active_run(self):
        store = create_in_memory_session_store()
        store.create_session("s1", AcpSessionMeta(session_id="s1"))
        assert store.cancel_active_run("s1") is None


class TestAcpAgentInfo:
    def test_defaults(self):
        info = AcpAgentInfo()
        assert info.name == "pyclaw"
        assert "chat" in info.capabilities


class TestAcpSessionMeta:
    def test_defaults(self):
        meta = AcpSessionMeta()
        assert meta.session_id == ""
        assert meta.agent_id == "main"
        assert meta.mode == "agent"
