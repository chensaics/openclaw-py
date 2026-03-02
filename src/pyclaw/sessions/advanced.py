"""Sessions advanced — send strategy, level/model overrides, transcript events, input sources.

Ported from ``src/sessions/*.ts`` and ``src/sessions/session-*.ts``.

Provides:
- Session send strategy (immediate, batched, queued)
- Level and model overrides per session
- Transcript event recording
- Input source tracking
- Session tags and metadata
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SendStrategy(str, Enum):
    IMMEDIATE = "immediate"
    BATCHED = "batched"
    QUEUED = "queued"


class InputSource(str, Enum):
    WEB = "web"
    CLI = "cli"
    CHANNEL = "channel"
    API = "api"
    CRON = "cron"
    INTERNAL = "internal"


class ThinkingLevel(str, Enum):
    DISABLED = "disabled"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class SessionOverrides:
    """Per-session overrides for model and behavior."""
    model: str = ""
    provider: str = ""
    temperature: float | None = None
    max_tokens: int | None = None
    thinking_level: ThinkingLevel = ThinkingLevel.DISABLED
    system_prompt_override: str = ""
    send_strategy: SendStrategy = SendStrategy.IMMEDIATE

    @property
    def has_model_override(self) -> bool:
        return bool(self.model)


@dataclass
class TranscriptEvent:
    """A recorded event in the session transcript."""
    event_type: str  # message | tool_call | tool_result | error | system
    timestamp: float = 0.0
    role: str = ""
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timestamp == 0:
            self.timestamp = time.time()


@dataclass
class SessionTag:
    """A tag on a session for filtering/grouping."""
    key: str
    value: str = ""
    created_at: float = 0.0

    def __post_init__(self) -> None:
        if self.created_at == 0:
            self.created_at = time.time()


@dataclass
class SessionMetadata:
    """Extended metadata for a session."""
    session_id: str
    agent_id: str = ""
    input_source: InputSource = InputSource.WEB
    channel_type: str = ""
    chat_id: str = ""
    overrides: SessionOverrides = field(default_factory=SessionOverrides)
    tags: list[SessionTag] = field(default_factory=list)
    transcript: list[TranscriptEvent] = field(default_factory=list)
    created_at: float = 0.0
    last_active_at: float = 0.0
    turn_count: int = 0
    total_tokens: int = 0

    def __post_init__(self) -> None:
        now = time.time()
        if self.created_at == 0:
            self.created_at = now
        if self.last_active_at == 0:
            self.last_active_at = now

    def touch(self) -> None:
        self.last_active_at = time.time()

    def add_tag(self, key: str, value: str = "") -> None:
        self.tags = [t for t in self.tags if t.key != key]
        self.tags.append(SessionTag(key=key, value=value))

    def get_tag(self, key: str) -> str | None:
        for t in self.tags:
            if t.key == key:
                return t.value
        return None

    def remove_tag(self, key: str) -> bool:
        before = len(self.tags)
        self.tags = [t for t in self.tags if t.key != key]
        return len(self.tags) < before

    def record_event(self, event: TranscriptEvent) -> None:
        self.transcript.append(event)
        self.touch()

    @property
    def transcript_count(self) -> int:
        return len(self.transcript)


class AdvancedSessionManager:
    """Manage sessions with overrides, tags, and transcripts."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionMetadata] = {}

    def get_or_create(
        self,
        session_id: str,
        *,
        agent_id: str = "",
        input_source: InputSource = InputSource.WEB,
    ) -> SessionMetadata:
        if session_id in self._sessions:
            meta = self._sessions[session_id]
            meta.touch()
            return meta

        meta = SessionMetadata(
            session_id=session_id,
            agent_id=agent_id,
            input_source=input_source,
        )
        self._sessions[session_id] = meta
        return meta

    def get(self, session_id: str) -> SessionMetadata | None:
        return self._sessions.get(session_id)

    def remove(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

    def set_overrides(
        self, session_id: str, overrides: SessionOverrides
    ) -> bool:
        meta = self._sessions.get(session_id)
        if not meta:
            return False
        meta.overrides = overrides
        meta.touch()
        return True

    def list_sessions(
        self,
        *,
        tag_filter: str = "",
        source_filter: InputSource | None = None,
    ) -> list[SessionMetadata]:
        result = list(self._sessions.values())
        if tag_filter:
            result = [s for s in result if any(t.key == tag_filter for t in s.tags)]
        if source_filter:
            result = [s for s in result if s.input_source == source_filter]
        return result

    @property
    def count(self) -> int:
        return len(self._sessions)


# ---------------------------------------------------------------------------
# Send strategy helpers
# ---------------------------------------------------------------------------

@dataclass
class BatchConfig:
    """Configuration for batched send strategy."""
    max_batch_size: int = 5
    batch_window_ms: float = 500.0
    flush_on_tool: bool = True


def resolve_send_strategy(
    overrides: SessionOverrides,
    *,
    is_streaming: bool = True,
) -> SendStrategy:
    """Resolve the effective send strategy."""
    if overrides.send_strategy != SendStrategy.IMMEDIATE:
        return overrides.send_strategy
    return SendStrategy.IMMEDIATE
