"""Embedded runner session manager — cache, history limits, lane resolution.

Ported from ``src/agents/pi-embedded-runner/session-manager*.ts`` and ``lanes.ts``.

Provides:
- Session cache with TTL and max entries
- Session initialization and restore
- Conversation history limiting (max messages, max tokens)
- Image pruning from older messages
- Lane resolution for multi-agent sessions
- Idle wait before flush
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pyclaw.agents.embedded_runner.run import Message, prune_images

logger = logging.getLogger(__name__)


@dataclass
class SessionConfig:
    """Configuration for the session manager."""
    max_history_messages: int = 100
    max_history_tokens: int = 100000
    max_cached_sessions: int = 20
    session_ttl_s: float = 3600.0
    image_keep_last_n: int = 2
    idle_wait_ms: float = 500.0


class SessionLane(str, Enum):
    """Session lane types for multi-agent routing."""
    DEFAULT = "default"
    PRIORITY = "priority"
    BACKGROUND = "background"
    CRON = "cron"


@dataclass
class SessionState:
    """State of an embedded runner session."""
    session_id: str
    agent_id: str = ""
    model: str = ""
    messages: list[Message] = field(default_factory=list)
    system_prompt: str = ""
    turn_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    created_at: float = 0.0
    last_active_at: float = 0.0
    lane: SessionLane = SessionLane.DEFAULT
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        now = time.time()
        if self.created_at == 0:
            self.created_at = now
        if self.last_active_at == 0:
            self.last_active_at = now

    def touch(self) -> None:
        self.last_active_at = time.time()

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def estimated_tokens(self) -> int:
        total = 0
        for msg in self.messages:
            if isinstance(msg.content, str):
                total += len(msg.content) // 4
            elif isinstance(msg.content, list):
                for block in msg.content:
                    if block.get("type") == "text":
                        total += len(block.get("text", "")) // 4
                    elif block.get("type") == "image_url":
                        total += 1000  # Rough estimate for images
        return total


class EmbeddedSessionManager:
    """Manage cached sessions for the embedded runner."""

    def __init__(self, config: SessionConfig | None = None) -> None:
        self._config = config or SessionConfig()
        self._sessions: dict[str, SessionState] = {}

    def get_or_create(
        self,
        session_id: str,
        *,
        agent_id: str = "",
        model: str = "",
        system_prompt: str = "",
        lane: SessionLane = SessionLane.DEFAULT,
    ) -> SessionState:
        """Get existing session or create a new one."""
        if session_id in self._sessions:
            session = self._sessions[session_id]
            session.touch()
            return session

        self._evict_if_needed()

        session = SessionState(
            session_id=session_id,
            agent_id=agent_id,
            model=model,
            system_prompt=system_prompt,
            lane=lane,
        )
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> SessionState | None:
        return self._sessions.get(session_id)

    def remove(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

    def append_message(self, session_id: str, message: Message) -> None:
        """Append a message and enforce history limits."""
        session = self._sessions.get(session_id)
        if not session:
            return

        session.messages.append(message)
        session.touch()

        self._enforce_history_limits(session)

    def _enforce_history_limits(self, session: SessionState) -> None:
        """Trim history to stay within configured limits."""
        msgs = session.messages

        # Keep system messages, trim oldest non-system messages
        while len(msgs) > self._config.max_history_messages:
            for i, m in enumerate(msgs):
                if m.role != "system":
                    msgs.pop(i)
                    break
            else:
                break

        # Prune images from older messages
        prune_images(msgs, keep_last_n=self._config.image_keep_last_n)

        # Rough token check
        if session.estimated_tokens > self._config.max_history_tokens:
            while len(msgs) > 2 and session.estimated_tokens > self._config.max_history_tokens:
                for i, m in enumerate(msgs):
                    if m.role != "system":
                        msgs.pop(i)
                        break
                else:
                    break

    def _evict_if_needed(self) -> None:
        """Evict oldest sessions if cache is full."""
        now = time.time()

        # First evict expired sessions
        expired = [
            sid for sid, s in self._sessions.items()
            if (now - s.last_active_at) > self._config.session_ttl_s
        ]
        for sid in expired:
            self._sessions.pop(sid, None)

        # Then evict oldest if still over limit
        while len(self._sessions) >= self._config.max_cached_sessions:
            oldest_sid = min(self._sessions, key=lambda s: self._sessions[s].last_active_at)
            self._sessions.pop(oldest_sid, None)

    @property
    def cached_count(self) -> int:
        return len(self._sessions)

    def list_sessions(self) -> list[SessionState]:
        return list(self._sessions.values())


# ---------------------------------------------------------------------------
# Lane Resolution
# ---------------------------------------------------------------------------

def resolve_lane(
    *,
    is_cron: bool = False,
    is_background: bool = False,
    is_priority: bool = False,
) -> SessionLane:
    """Resolve the session lane based on context."""
    if is_priority:
        return SessionLane.PRIORITY
    if is_cron:
        return SessionLane.CRON
    if is_background:
        return SessionLane.BACKGROUND
    return SessionLane.DEFAULT


def should_wait_for_idle(lane: SessionLane) -> bool:
    """Whether this lane should wait for idle before flushing."""
    return lane in (SessionLane.DEFAULT, SessionLane.PRIORITY)
