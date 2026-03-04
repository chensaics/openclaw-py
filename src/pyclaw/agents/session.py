"""Session manager — JSONL-based session persistence.

Compatible with the TypeScript SessionManager format:
- Each line is a JSON object with a "type" field
- Types: "session" (header), "message", "compaction", "custom", "session-meta"
- Messages follow the LLM message format: {role, content, ...}
- Each entry carries ``id`` and ``parentId`` forming a DAG (tree)
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from pyclaw.agents.tokens import estimate_messages_tokens


def _gen_id() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Timeline types (F06 — message-level activity timeline)
# ---------------------------------------------------------------------------


class TimelineKind(str, Enum):
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    STATUS = "status"
    PLAN = "plan"
    INTERRUPT = "interrupt"


@dataclass
class TimelineActivity:
    """A discrete activity record within a message timeline."""

    activity_type: str  # "tool_exec" | "plan_step" | "interrupt" | ...
    summary: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "type": self.activity_type,
            "summary": self.summary,
            "timestamp": self.timestamp,
        }
        if self.detail:
            d["detail"] = self.detail
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TimelineActivity:
        return cls(
            activity_type=data.get("type", ""),
            summary=data.get("summary", ""),
            detail=data.get("detail", ""),
            timestamp=data.get("timestamp", 0.0),
        )


@dataclass
class TimelineEntry:
    """A single timeline entry embedding an activity into a message."""

    kind: TimelineKind
    activity: TimelineActivity

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "activity": self.activity.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TimelineEntry:
        return cls(
            kind=TimelineKind(data.get("kind", "status")),
            activity=TimelineActivity.from_dict(data.get("activity", {})),
        )


# ---------------------------------------------------------------------------
# Agent message
# ---------------------------------------------------------------------------


@dataclass
class AgentMessage:
    """A message in the agent conversation."""

    role: str  # "user" | "assistant" | "tool" | "system"
    content: str | list[dict[str, Any]]
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    name: str | None = None
    timeline: list[TimelineEntry] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
        if self.tool_calls is not None:
            d["tool_calls"] = self.tool_calls
        if self.name is not None:
            d["name"] = self.name
        if self.timeline:
            d["timeline"] = [e.to_dict() for e in self.timeline]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentMessage:
        timeline_raw = data.get("timeline")
        timeline = [TimelineEntry.from_dict(e) for e in timeline_raw] if timeline_raw else None
        return cls(
            role=data["role"],
            content=data["content"],
            tool_call_id=data.get("tool_call_id"),
            tool_calls=data.get("tool_calls"),
            name=data.get("name"),
            timeline=timeline,
        )

    def add_timeline(self, kind: TimelineKind, summary: str, **kwargs: Any) -> None:
        """Append a timeline entry to this message."""
        if self.timeline is None:
            self.timeline = []
        self.timeline.append(
            TimelineEntry(
                kind=kind,
                activity=TimelineActivity(
                    activity_type=kind.value,
                    summary=summary,
                    **kwargs,
                ),
            )
        )


@dataclass
class SessionManager:
    """JSONL-based session file manager.

    Reads and writes session transcript files compatible with the
    TypeScript pi-coding-agent SessionManager format.  Supports DAG
    entries (id/parentId) and simple compaction.
    """

    path: Path
    session_id: str = field(default_factory=_gen_id)
    messages: list[AgentMessage] = field(default_factory=list)
    custom_entries: list[dict[str, Any]] = field(default_factory=list)
    compaction_count: int = 0
    _loaded: bool = field(default=False, repr=False)
    _leaf_id: str | None = field(default=None, repr=False)

    # ---- loading ----

    def load(self) -> None:
        """Load an existing JSONL session file."""
        self.messages.clear()
        self.custom_entries.clear()
        self.compaction_count = 0
        self._leaf_id = None

        if not self.path.exists():
            self._loaded = True
            return

        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                entry_type = entry.get("type")
                entry_id = entry.get("id")

                if entry_type == "session":
                    if sid := entry.get("id"):
                        self.session_id = sid
                elif entry_type == "message":
                    msg_data = entry.get("message", {})
                    self.messages.append(AgentMessage.from_dict(msg_data))
                elif entry_type == "compaction":
                    # Compaction replaces earlier messages with a summary
                    summary = entry.get("summary", "")
                    entry.get("firstKeptEntryId")
                    self.compaction_count += 1
                    # Keep the summary as a system message in the active window
                    if summary:
                        self.messages.insert(
                            0,
                            AgentMessage(
                                role="system",
                                content=f"[Previous conversation summary]\n{summary}",
                            ),
                        )
                elif entry_type == "custom":
                    self.custom_entries.append(entry)

                if entry_id:
                    self._leaf_id = entry_id

        self._loaded = True

    # ---- appending ----

    def append_message(self, message: AgentMessage) -> None:
        """Append a message to the session and persist to disk."""
        self.messages.append(message)
        entry_id = _gen_id()
        entry: dict[str, Any] = {
            "type": "message",
            "id": entry_id,
            "message": message.to_dict(),
        }
        if self._leaf_id:
            entry["parentId"] = self._leaf_id
        self._leaf_id = entry_id
        self._append_line(entry)

    def append_custom(self, custom_type: str, data: dict[str, Any]) -> None:
        """Append a custom entry to the session file."""
        entry_id = _gen_id()
        entry: dict[str, Any] = {
            "type": "custom",
            "id": entry_id,
            "customType": custom_type,
            "data": data,
        }
        if self._leaf_id:
            entry["parentId"] = self._leaf_id
        self._leaf_id = entry_id
        self.custom_entries.append(entry)
        self._append_line(entry)

    def write_header(self) -> None:
        """Write the session header line (typically first line of a new session)."""
        self._append_line(
            {
                "type": "session",
                "version": 3,
                "id": self.session_id,
            }
        )

    # ---- compaction ----

    def compact(self, summary: str, keep_last_n: int = 4) -> dict[str, int]:
        """Compact the session by replacing old messages with a summary.

        Keeps the last ``keep_last_n`` messages intact.  Returns token
        counts before and after compaction.
        """
        all_dicts = self.get_messages_as_dicts()
        tokens_before = estimate_messages_tokens(all_dicts)

        if len(self.messages) <= keep_last_n:
            return {"tokens_before": tokens_before, "tokens_after": tokens_before}

        kept = self.messages[-keep_last_n:]
        self.messages.clear()
        self.messages.append(
            AgentMessage(
                role="system",
                content=f"[Previous conversation summary]\n{summary}",
            )
        )
        self.messages.extend(kept)
        self.compaction_count += 1

        tokens_after = estimate_messages_tokens(self.get_messages_as_dicts())

        entry_id = _gen_id()
        compaction_entry: dict[str, Any] = {
            "type": "compaction",
            "id": entry_id,
            "summary": summary,
            "tokensBefore": tokens_before,
            "tokensAfter": tokens_after,
        }
        if self._leaf_id:
            compaction_entry["parentId"] = self._leaf_id
        self._leaf_id = entry_id
        self._append_line(compaction_entry)

        return {"tokens_before": tokens_before, "tokens_after": tokens_after}

    def estimate_tokens(self) -> int:
        """Estimate total tokens for the current message window."""
        return estimate_messages_tokens(self.get_messages_as_dicts())

    # ---- accessors ----

    def get_messages_as_dicts(self) -> list[dict[str, Any]]:
        """Return all messages as plain dicts for LLM API calls."""
        return [m.to_dict() for m in self.messages]

    # ---- internal ----

    def _append_line(self, entry: dict[str, Any]) -> None:
        if str(self.path) == "/dev/null":
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ---- factories ----

    @classmethod
    def open(cls, path: Path) -> SessionManager:
        """Open (or create) a session file and load its contents."""
        mgr = cls(path=path)
        mgr.load()
        return mgr

    @classmethod
    def in_memory(cls) -> SessionManager:
        """Create an in-memory session manager (no file persistence)."""
        mgr = cls(path=Path("/dev/null"))
        mgr._loaded = True
        return mgr


def load_sessions_index(sessions_json_path: Path) -> dict[str, Any]:
    """Load the sessions.json index file."""
    if not sessions_json_path.exists():
        return {}
    with open(sessions_json_path, encoding="utf-8") as f:
        result: dict[str, Any] = json.load(f)
        return result


def save_sessions_index(sessions_json_path: Path, data: dict[str, Any]) -> None:
    """Save the sessions.json index file atomically."""
    sessions_json_path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    tmp = sessions_json_path.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.rename(sessions_json_path)
