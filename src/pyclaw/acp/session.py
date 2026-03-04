"""ACP session store — in-memory session management with TTL and eviction."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from pyclaw.acp.types import AcpSessionMeta


@dataclass
class AcpSession:
    meta: AcpSessionMeta
    active_run_id: str | None = None
    messages: list[dict[str, Any]] = field(default_factory=list)
    last_activity: float = 0.0


class AcpSessionStore:
    """In-memory session store with max sessions and idle TTL."""

    def __init__(self, max_sessions: int = 50, idle_ttl_s: float = 3600) -> None:
        self._sessions: dict[str, AcpSession] = {}
        self._max_sessions = max_sessions
        self._idle_ttl = idle_ttl_s

    def create_session(self, session_id: str, meta: AcpSessionMeta) -> AcpSession:
        self._evict_if_needed()
        meta.created_at = time.time()
        session = AcpSession(meta=meta, last_activity=time.time())
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> AcpSession | None:
        s = self._sessions.get(session_id)
        if s:
            s.last_activity = time.time()
        return s

    def has_session(self, session_id: str) -> bool:
        return session_id in self._sessions

    def list_sessions(self) -> list[AcpSession]:
        return list(self._sessions.values())

    def remove_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def set_active_run(self, session_id: str, run_id: str) -> None:
        s = self._sessions.get(session_id)
        if s:
            s.active_run_id = run_id

    def clear_active_run(self, session_id: str) -> None:
        s = self._sessions.get(session_id)
        if s:
            s.active_run_id = None

    def cancel_active_run(self, session_id: str) -> str | None:
        s = self._sessions.get(session_id)
        if s and s.active_run_id:
            run_id = s.active_run_id
            s.active_run_id = None
            return run_id
        return None

    def _evict_if_needed(self) -> None:
        now = time.time()
        expired = [sid for sid, s in self._sessions.items() if (now - s.last_activity) > self._idle_ttl]
        for sid in expired:
            del self._sessions[sid]

        while len(self._sessions) >= self._max_sessions:
            oldest = min(self._sessions, key=lambda k: self._sessions[k].last_activity)
            del self._sessions[oldest]


def create_in_memory_session_store(
    max_sessions: int = 50,
    idle_ttl_s: float = 3600,
) -> AcpSessionStore:
    return AcpSessionStore(max_sessions=max_sessions, idle_ttl_s=idle_ttl_s)
