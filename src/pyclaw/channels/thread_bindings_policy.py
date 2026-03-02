"""Thread bindings policy — generic idle/max-age TTL for thread-bound sessions.

Ported from ``src/channels/thread-bindings-policy.ts`` and
``src/discord/monitor/``.

Provides the core TTL mechanism used by Discord (and potentially other
threaded channels) to automatically unbind inactive thread sessions.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_IDLE_HOURS = 24.0
DEFAULT_MAX_AGE_HOURS = 0.0  # 0 = disabled
SWEEP_INTERVAL_S = 60.0


@dataclass
class ThreadBindingConfig:
    """TTL configuration for thread bindings."""

    idle_hours: float = DEFAULT_IDLE_HOURS
    max_age_hours: float = DEFAULT_MAX_AGE_HOURS


@dataclass
class ThreadBindingRecord:
    """A single thread-to-session binding."""

    thread_id: str
    session_key: str
    channel_id: str = ""
    bound_at: float = 0.0
    last_activity_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        now = time.time()
        if self.bound_at == 0.0:
            self.bound_at = now
        if self.last_activity_at == 0.0:
            self.last_activity_at = now


def check_expiry(
    record: ThreadBindingRecord,
    idle_hours: float = DEFAULT_IDLE_HOURS,
    max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
) -> str | None:
    """Check if a thread binding has expired.

    Returns the expiry reason ("idle-expired" or "max-age-expired") or None.
    """
    now = time.time()

    if idle_hours > 0:
        idle_expires_at = record.last_activity_at + idle_hours * 3600
        if now >= idle_expires_at:
            return "idle-expired"

    if max_age_hours > 0:
        age_expires_at = record.bound_at + max_age_hours * 3600
        if now >= age_expires_at:
            return "max-age-expired"

    return None


def resolve_thread_binding_config(
    *,
    session_config: dict[str, Any] | None = None,
    channel_config: dict[str, Any] | None = None,
    account_config: dict[str, Any] | None = None,
) -> ThreadBindingConfig:
    """Resolve thread binding TTL from config layers (account > channel > session)."""
    idle_hours: float | None = None
    max_age_hours: float | None = None

    # Resolve each field independently across layers (account > channel > session)
    for cfg in [account_config, channel_config, session_config]:
        if not cfg:
            continue
        tb = cfg.get("threadBindings", {})
        if idle_hours is None and "idleHours" in tb:
            idle_hours = float(tb["idleHours"])
        if max_age_hours is None and "maxAgeHours" in tb:
            max_age_hours = float(tb["maxAgeHours"])

    return ThreadBindingConfig(
        idle_hours=idle_hours if idle_hours is not None else DEFAULT_IDLE_HOURS,
        max_age_hours=max_age_hours if max_age_hours is not None else DEFAULT_MAX_AGE_HOURS,
    )


# ---------------------------------------------------------------------------
# Thread binding store
# ---------------------------------------------------------------------------

UnbindCallback = Callable[[ThreadBindingRecord, str], Coroutine[Any, Any, None]]


class ThreadBindingStore:
    """In-memory store for thread-to-session bindings with TTL sweep."""

    def __init__(self, config: ThreadBindingConfig | None = None) -> None:
        self._bindings: dict[str, ThreadBindingRecord] = {}
        self._config = config or ThreadBindingConfig()
        self._sweep_task: asyncio.Task[None] | None = None
        self._on_unbind: UnbindCallback | None = None

    def bind(
        self,
        thread_id: str,
        session_key: str,
        *,
        channel_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ThreadBindingRecord:
        """Create or update a thread binding."""
        existing = self._bindings.get(thread_id)
        if existing:
            existing.session_key = session_key
            existing.last_activity_at = time.time()
            return existing

        record = ThreadBindingRecord(
            thread_id=thread_id,
            session_key=session_key,
            channel_id=channel_id,
            metadata=metadata or {},
        )
        self._bindings[thread_id] = record
        return record

    def unbind(self, thread_id: str) -> ThreadBindingRecord | None:
        """Remove a thread binding."""
        return self._bindings.pop(thread_id, None)

    def touch(self, thread_id: str) -> None:
        """Update last activity time for a thread binding."""
        record = self._bindings.get(thread_id)
        if record:
            record.last_activity_at = time.time()

    def get(self, thread_id: str) -> ThreadBindingRecord | None:
        return self._bindings.get(thread_id)

    def list_all(self) -> list[ThreadBindingRecord]:
        return list(self._bindings.values())

    @property
    def count(self) -> int:
        return len(self._bindings)

    def set_unbind_callback(self, callback: UnbindCallback) -> None:
        self._on_unbind = callback

    async def start_sweep(self) -> None:
        """Start the periodic sweep loop."""
        if self._sweep_task and not self._sweep_task.done():
            return
        self._sweep_task = asyncio.create_task(self._sweep_loop())

    async def stop_sweep(self) -> None:
        """Stop the periodic sweep loop."""
        if self._sweep_task:
            self._sweep_task.cancel()
            try:
                await self._sweep_task
            except asyncio.CancelledError:
                pass
            self._sweep_task = None

    async def sweep_once(self) -> list[tuple[ThreadBindingRecord, str]]:
        """Run a single sweep, returning expired bindings with reasons."""
        expired: list[tuple[ThreadBindingRecord, str]] = []

        for thread_id in list(self._bindings.keys()):
            record = self._bindings.get(thread_id)
            if not record:
                continue

            reason = check_expiry(
                record,
                idle_hours=self._config.idle_hours,
                max_age_hours=self._config.max_age_hours,
            )
            if reason:
                self._bindings.pop(thread_id, None)
                expired.append((record, reason))
                if self._on_unbind:
                    try:
                        await self._on_unbind(record, reason)
                    except Exception:
                        logger.warning("Unbind callback failed for %s", thread_id)

        return expired

    async def _sweep_loop(self) -> None:
        """Periodically sweep expired bindings."""
        try:
            while True:
                await asyncio.sleep(SWEEP_INTERVAL_S)
                expired = await self.sweep_once()
                if expired:
                    logger.info(
                        "Thread sweep: removed %d expired bindings",
                        len(expired),
                    )
        except asyncio.CancelledError:
            pass
