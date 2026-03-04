"""Typing indicator manager — cross-channel unified lifecycle with safety nets.

Ported from ``src/channels/typing.ts``.

Provides a unified typing indicator system that works across all channels,
with TTL safety nets, circuit breakers for API failures, and run-scoped
lifecycle management to prevent stuck indicators.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_KEEPALIVE_INTERVAL_S = 4.0
DEFAULT_MAX_DURATION_S = 300.0
DEFAULT_CIRCUIT_BREAKER_THRESHOLD = 3
DEFAULT_CIRCUIT_BREAKER_RESET_S = 60.0


@dataclass
class TypingConfig:
    """Typing indicator configuration."""

    keepalive_interval_s: float = DEFAULT_KEEPALIVE_INTERVAL_S
    max_duration_s: float = DEFAULT_MAX_DURATION_S
    circuit_breaker_threshold: int = DEFAULT_CIRCUIT_BREAKER_THRESHOLD
    circuit_breaker_reset_s: float = DEFAULT_CIRCUIT_BREAKER_RESET_S


TypingCallback = Callable[[], Coroutine[Any, Any, None]]


class TypingCircuitBreaker:
    """Stops typing API calls after consecutive failures."""

    def __init__(
        self,
        threshold: int = DEFAULT_CIRCUIT_BREAKER_THRESHOLD,
        reset_s: float = DEFAULT_CIRCUIT_BREAKER_RESET_S,
    ) -> None:
        self._threshold = threshold
        self._reset_s = reset_s
        self._consecutive_failures = 0
        self._last_failure_at = 0.0
        self._open = False

    @property
    def is_open(self) -> bool:
        if self._open and time.time() - self._last_failure_at > self._reset_s:
            self._open = False
            self._consecutive_failures = 0
            return False
        return self._open

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._open = False

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        self._last_failure_at = time.time()
        if self._consecutive_failures >= self._threshold:
            self._open = True
            logger.warning(
                "Typing circuit breaker opened after %d failures",
                self._consecutive_failures,
            )


@dataclass
class TypingSession:
    """A single typing indicator session for one channel+chat."""

    channel_id: str
    chat_id: str
    callback: TypingCallback
    started_at: float = 0.0
    run_complete: bool = False
    dispatch_idle: bool = False
    _task: asyncio.Task[None] | None = field(default=None, repr=False)
    _circuit_breaker: TypingCircuitBreaker = field(default_factory=TypingCircuitBreaker, repr=False)
    _sealed: bool = False

    def __post_init__(self) -> None:
        if self.started_at == 0.0:
            self.started_at = time.time()


class TypingManager:
    """Manages typing indicators across all channels with safety guarantees."""

    def __init__(self, config: TypingConfig | None = None) -> None:
        self._config = config or TypingConfig()
        self._sessions: dict[str, TypingSession] = {}

    def _key(self, channel_id: str, chat_id: str) -> str:
        return f"{channel_id}:{chat_id}"

    async def start_typing(
        self,
        channel_id: str,
        chat_id: str,
        callback: TypingCallback,
    ) -> TypingSession:
        """Start a typing indicator for a channel+chat pair.

        Returns the session object for lifecycle control.
        """
        key = self._key(channel_id, chat_id)

        existing = self._sessions.get(key)
        if existing and existing._task and not existing._task.done():
            return existing

        session = TypingSession(
            channel_id=channel_id,
            chat_id=chat_id,
            callback=callback,
        )
        self._sessions[key] = session

        # Fire initial typing
        await self._safe_trigger(session)

        # Start keepalive loop
        session._task = asyncio.create_task(self._keepalive_loop(key, session))
        return session

    async def stop_typing(self, channel_id: str, chat_id: str) -> None:
        """Stop typing for a channel+chat pair."""
        key = self._key(channel_id, chat_id)
        session = self._sessions.pop(key, None)
        if session:
            session._sealed = True
            if session._task and not session._task.done():
                session._task.cancel()
                try:
                    await session._task
                except asyncio.CancelledError:
                    pass

    def mark_run_complete(self, channel_id: str, chat_id: str) -> None:
        """Mark that the agent run is complete — typing will stop after dispatch idle."""
        key = self._key(channel_id, chat_id)
        session = self._sessions.get(key)
        if session:
            session.run_complete = True

    async def mark_dispatch_idle(self, channel_id: str, chat_id: str) -> None:
        """Mark dispatch as idle — stops typing if run is complete."""
        key = self._key(channel_id, chat_id)
        session = self._sessions.get(key)
        if session:
            session.dispatch_idle = True
            if session.run_complete:
                await self.stop_typing(channel_id, chat_id)

    async def force_cleanup(self, channel_id: str, chat_id: str) -> None:
        """Force cleanup — always stops typing regardless of state."""
        await self.stop_typing(channel_id, chat_id)

    async def stop_all(self) -> None:
        """Stop all active typing sessions."""
        keys = list(self._sessions.keys())
        for key in keys:
            session = self._sessions.pop(key, None)
            if session:
                session._sealed = True
                if session._task and not session._task.done():
                    session._task.cancel()

    @property
    def active_count(self) -> int:
        return len(self._sessions)

    async def _keepalive_loop(self, key: str, session: TypingSession) -> None:
        """Periodic keepalive loop with TTL safety net."""
        try:
            while True:
                await asyncio.sleep(self._config.keepalive_interval_s)

                if session._sealed:
                    break

                # TTL safety net
                elapsed = time.time() - session.started_at
                if elapsed > self._config.max_duration_s:
                    logger.info(
                        "Typing TTL expired for %s:%s (%.0fs)",
                        session.channel_id,
                        session.chat_id,
                        elapsed,
                    )
                    break

                # Guard against post-run keepalive
                if session.run_complete:
                    break

                await self._safe_trigger(session)

        except asyncio.CancelledError:
            pass
        finally:
            self._sessions.pop(key, None)

    async def _safe_trigger(self, session: TypingSession) -> None:
        """Trigger typing callback with circuit breaker protection."""
        if session._sealed or session._circuit_breaker.is_open:
            return

        try:
            await session.callback()
            session._circuit_breaker.record_success()
        except Exception:
            session._circuit_breaker.record_failure()
            logger.debug(
                "Typing callback failed for %s:%s",
                session.channel_id,
                session.chat_id,
            )
