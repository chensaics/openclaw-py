"""Draft streaming control — finalizable drafts, throttle, stop/clear.

Ported from ``src/channels/channel-plugin-sdk/draft-stream*.ts``.

Provides:
- DraftStream lifecycle (start → update → finalize / clear)
- Throttled updates to avoid API rate limits
- Stop/clear semantics
- Channel streaming interface
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class DraftState(str, Enum):
    IDLE = "idle"
    STREAMING = "streaming"
    FINALIZING = "finalizing"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class DraftConfig:
    """Configuration for draft streaming."""

    throttle_ms: int = 300
    min_update_chars: int = 10
    max_pending_updates: int = 5
    finalize_timeout_s: float = 30.0
    clear_on_error: bool = True


@dataclass
class DraftUpdate:
    """A pending draft update."""

    text: str
    timestamp: float = 0.0
    is_final: bool = False

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()


UpdateFn = Callable[[str, str], Coroutine[Any, Any, bool]]  # (draft_id, text) -> success
FinalizeFn = Callable[[str, str], Coroutine[Any, Any, str]]  # (draft_id, text) -> message_id


class DraftStream:
    """Manages a single draft streaming session.

    Lifecycle: start() → feed() ... → finalize() or clear()
    Updates are throttled to avoid overwhelming the channel API.
    """

    def __init__(
        self,
        draft_id: str,
        chat_id: str,
        *,
        config: DraftConfig | None = None,
        on_update: UpdateFn | None = None,
        on_finalize: FinalizeFn | None = None,
    ) -> None:
        self._draft_id = draft_id
        self._chat_id = chat_id
        self._config = config or DraftConfig()
        self._on_update = on_update
        self._on_finalize = on_finalize

        self._state = DraftState.IDLE
        self._buffer = ""
        self._last_sent = ""
        self._last_update_time = 0.0
        self._update_count = 0
        self._throttle_task: asyncio.Task[None] | None = None

    @property
    def draft_id(self) -> str:
        return self._draft_id

    @property
    def state(self) -> DraftState:
        return self._state

    @property
    def update_count(self) -> int:
        return self._update_count

    def start(self) -> None:
        """Start the draft stream."""
        self._state = DraftState.STREAMING

    async def feed(self, text: str) -> None:
        """Feed new text into the draft buffer."""
        if self._state != DraftState.STREAMING:
            return

        self._buffer = text
        now = time.time()
        elapsed_ms = (now - self._last_update_time) * 1000

        if elapsed_ms >= self._config.throttle_ms:
            await self._flush_update()
        # Otherwise the throttle cycle will pick it up

    async def _flush_update(self) -> None:
        """Send the current buffer as a draft update."""
        if self._buffer == self._last_sent:
            return
        if len(self._buffer) - len(self._last_sent) < self._config.min_update_chars:
            if not self._buffer.endswith("\n"):
                return

        text = self._buffer
        self._last_sent = text
        self._last_update_time = time.time()
        self._update_count += 1

        if self._on_update:
            try:
                await self._on_update(self._draft_id, text)
            except Exception as e:
                logger.error("Draft update error: %s", e)
                if self._config.clear_on_error:
                    self._state = DraftState.ERROR

    async def finalize(self, final_text: str | None = None) -> str:
        """Finalize the draft with the complete text. Returns message_id."""
        self._state = DraftState.FINALIZING
        text = final_text or self._buffer

        if self._on_finalize:
            try:
                message_id = await self._on_finalize(self._draft_id, text)
                self._state = DraftState.IDLE
                return message_id
            except Exception as e:
                logger.error("Draft finalize error: %s", e)
                self._state = DraftState.ERROR
                return ""

        self._state = DraftState.IDLE
        return ""

    def stop(self) -> None:
        """Stop the draft stream without finalizing."""
        self._state = DraftState.STOPPED
        if self._throttle_task and not self._throttle_task.done():
            self._throttle_task.cancel()

    def clear(self) -> None:
        """Clear the draft buffer and reset state."""
        self._buffer = ""
        self._last_sent = ""
        self._state = DraftState.IDLE
        self._update_count = 0

    @property
    def current_text(self) -> str:
        return self._buffer


# ---------------------------------------------------------------------------
# Draft Stream Manager (per-channel)
# ---------------------------------------------------------------------------


class DraftStreamManager:
    """Manages multiple concurrent draft streams for a channel."""

    def __init__(self, config: DraftConfig | None = None) -> None:
        self._config = config or DraftConfig()
        self._streams: dict[str, DraftStream] = {}

    def create(
        self,
        draft_id: str,
        chat_id: str,
        *,
        on_update: UpdateFn | None = None,
        on_finalize: FinalizeFn | None = None,
    ) -> DraftStream:
        stream = DraftStream(
            draft_id,
            chat_id,
            config=self._config,
            on_update=on_update,
            on_finalize=on_finalize,
        )
        self._streams[draft_id] = stream
        return stream

    def get(self, draft_id: str) -> DraftStream | None:
        return self._streams.get(draft_id)

    def remove(self, draft_id: str) -> bool:
        stream = self._streams.pop(draft_id, None)
        if stream:
            stream.stop()
            return True
        return False

    def stop_all(self) -> int:
        count = len(self._streams)
        for stream in self._streams.values():
            stream.stop()
        self._streams.clear()
        return count

    @property
    def active_count(self) -> int:
        return sum(1 for s in self._streams.values() if s.state == DraftState.STREAMING)

    def list_active(self) -> list[str]:
        return [did for did, s in self._streams.items() if s.state == DraftState.STREAMING]
