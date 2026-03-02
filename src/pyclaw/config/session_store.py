"""Session store — file/metadata/transcript/artifact/delivery management.

Ported from ``src/config/session-store*.ts``.

Provides:
- Session file management (create/read/update/delete)
- Session metadata tracking
- Transcript storage
- Artifact management
- Delivery info persistence
- Disk budget enforcement
- Cache field management
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MAX_SESSIONS = 100
DEFAULT_DISK_BUDGET_MB = 500


@dataclass
class SessionMetadata:
    """Metadata for a stored session."""
    session_id: str
    agent_id: str = ""
    model: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0
    turn_count: int = 0
    token_count: int = 0
    status: str = "active"       # "active" | "idle" | "archived"
    channel_id: str = ""
    sender_id: str = ""
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        now = time.time()
        if self.created_at == 0.0:
            self.created_at = now
        if self.updated_at == 0.0:
            self.updated_at = now


@dataclass
class DeliveryInfo:
    """Delivery tracking for a session message."""
    message_id: str
    channel_id: str
    chat_id: str
    delivered_at: float = 0.0
    status: str = "delivered"    # "delivered" | "failed" | "pending"
    error: str = ""


@dataclass
class SessionArtifact:
    """An artifact attached to a session (files, images, etc.)."""
    artifact_id: str
    session_id: str
    filename: str
    mime_type: str = ""
    size_bytes: int = 0
    created_at: float = 0.0
    path: str = ""


@dataclass
class StoreConfig:
    """Configuration for the session store."""
    base_dir: str
    max_sessions: int = DEFAULT_MAX_SESSIONS
    disk_budget_mb: int = DEFAULT_DISK_BUDGET_MB
    auto_archive_days: int = 30


class SessionStore:
    """Manage session files, metadata, and artifacts on disk."""

    def __init__(self, config: StoreConfig) -> None:
        self._config = config
        self._metadata_cache: dict[str, SessionMetadata] = {}
        os.makedirs(config.base_dir, exist_ok=True)

    def _session_dir(self, session_id: str) -> str:
        return os.path.join(self._config.base_dir, session_id)

    def _metadata_path(self, session_id: str) -> str:
        return os.path.join(self._session_dir(session_id), "metadata.json")

    def _transcript_path(self, session_id: str) -> str:
        return os.path.join(self._session_dir(session_id), "transcript.jsonl")

    def _delivery_path(self, session_id: str) -> str:
        return os.path.join(self._session_dir(session_id), "delivery.jsonl")

    # -- Session lifecycle --

    def create_session(self, metadata: SessionMetadata) -> str:
        """Create a new session. Returns the session directory path."""
        session_dir = self._session_dir(metadata.session_id)
        os.makedirs(session_dir, exist_ok=True)

        self._write_metadata(metadata)
        self._metadata_cache[metadata.session_id] = metadata
        return session_dir

    def get_metadata(self, session_id: str) -> SessionMetadata | None:
        """Get session metadata (from cache or disk)."""
        if session_id in self._metadata_cache:
            return self._metadata_cache[session_id]

        path = self._metadata_path(session_id)
        if not os.path.exists(path):
            return None

        try:
            with open(path) as f:
                data = json.load(f)
            meta = SessionMetadata(**data)
            self._metadata_cache[session_id] = meta
            return meta
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Failed to load metadata for %s: %s", session_id, e)
            return None

    def update_metadata(self, session_id: str, **kwargs: Any) -> bool:
        """Update session metadata fields."""
        meta = self.get_metadata(session_id)
        if not meta:
            return False

        for key, value in kwargs.items():
            if hasattr(meta, key):
                setattr(meta, key, value)

        meta.updated_at = time.time()
        self._write_metadata(meta)
        self._metadata_cache[session_id] = meta
        return True

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its files."""
        session_dir = self._session_dir(session_id)
        if not os.path.isdir(session_dir):
            return False

        import shutil
        shutil.rmtree(session_dir, ignore_errors=True)
        self._metadata_cache.pop(session_id, None)
        return True

    def _write_metadata(self, metadata: SessionMetadata) -> None:
        path = self._metadata_path(metadata.session_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {
            k: v for k, v in metadata.__dict__.items()
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    # -- Transcript --

    def append_transcript(self, session_id: str, entry: dict[str, Any]) -> None:
        """Append a transcript entry (JSONL)."""
        path = self._transcript_path(session_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def read_transcript(self, session_id: str, *, limit: int = 0) -> list[dict[str, Any]]:
        """Read transcript entries."""
        path = self._transcript_path(session_id)
        if not os.path.exists(path):
            return []

        entries: list[dict[str, Any]] = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        if limit > 0:
            entries = entries[-limit:]
        return entries

    # -- Delivery --

    def record_delivery(self, session_id: str, info: DeliveryInfo) -> None:
        """Record a delivery event."""
        path = self._delivery_path(session_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = info.__dict__
        with open(path, "a") as f:
            f.write(json.dumps(data) + "\n")

    # -- Listing --

    def list_sessions(
        self,
        *,
        status: str = "",
        limit: int = 0,
    ) -> list[SessionMetadata]:
        """List sessions with optional filtering."""
        sessions: list[SessionMetadata] = []
        base = self._config.base_dir

        if not os.path.isdir(base):
            return []

        for entry in os.scandir(base):
            if not entry.is_dir():
                continue
            meta = self.get_metadata(entry.name)
            if meta:
                if status and meta.status != status:
                    continue
                sessions.append(meta)

        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        if limit > 0:
            sessions = sessions[:limit]
        return sessions

    # -- Disk budget --

    def get_disk_usage_mb(self) -> float:
        """Calculate total disk usage in MB."""
        total = 0
        base = self._config.base_dir
        if not os.path.isdir(base):
            return 0.0

        for dirpath, _, filenames in os.walk(base):
            for f in filenames:
                try:
                    total += os.path.getsize(os.path.join(dirpath, f))
                except OSError:
                    pass

        return total / (1024 * 1024)

    def is_over_budget(self) -> bool:
        return self.get_disk_usage_mb() > self._config.disk_budget_mb

    @property
    def session_count(self) -> int:
        base = self._config.base_dir
        if not os.path.isdir(base):
            return 0
        return sum(1 for e in os.scandir(base) if e.is_dir())
