"""System events — event bus, presence, heartbeat visibility, wake events.

Ported from ``src/infra/system-events.ts``, ``system-presence.ts``.

Provides:
- System-level event bus with typed events
- Presence (online/offline/idle) management
- Heartbeat visibility tracking
- Wake event handling (sleep/wake transitions)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    GATEWAY_START = "gateway.start"
    GATEWAY_STOP = "gateway.stop"
    CHANNEL_CONNECT = "channel.connect"
    CHANNEL_DISCONNECT = "channel.disconnect"
    AGENT_START = "agent.start"
    AGENT_STOP = "agent.stop"
    SESSION_CREATE = "session.create"
    SESSION_END = "session.end"
    CONFIG_RELOAD = "config.reload"
    SYSTEM_WAKE = "system.wake"
    SYSTEM_SLEEP = "system.sleep"
    HEALTH_CHECK = "health.check"
    ERROR = "error"


class PresenceState(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    IDLE = "idle"
    AWAY = "away"


@dataclass
class SystemEvent:
    """A system-level event."""
    event_type: EventType
    source: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0:
            self.timestamp = time.time()


EventHandler = Callable[[SystemEvent], None]


class EventBus:
    """Publish/subscribe event bus for system events."""

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[EventHandler]] = {}
        self._global_handlers: list[EventHandler] = []
        self._history: list[SystemEvent] = []
        self._max_history = 100

    def on(self, event_type: EventType, handler: EventHandler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def on_all(self, handler: EventHandler) -> None:
        self._global_handlers.append(handler)

    def off(self, event_type: EventType, handler: EventHandler) -> None:
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    def emit(self, event: SystemEvent) -> None:
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        for handler in self._handlers.get(event.event_type, []):
            try:
                handler(event)
            except Exception as e:
                logger.error("Event handler error for %s: %s", event.event_type, e)

        for handler in self._global_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error("Global event handler error: %s", e)

    def recent(self, limit: int = 20) -> list[SystemEvent]:
        return self._history[-limit:]

    def clear_history(self) -> None:
        self._history.clear()

    @property
    def handler_count(self) -> int:
        return sum(len(h) for h in self._handlers.values()) + len(self._global_handlers)


# ---------------------------------------------------------------------------
# Presence Manager
# ---------------------------------------------------------------------------

@dataclass
class PresenceInfo:
    """Presence information for a component."""
    component_id: str
    state: PresenceState = PresenceState.OFFLINE
    last_seen_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class PresenceManager:
    """Track online/offline presence of components."""

    def __init__(self, *, idle_timeout_s: float = 300.0) -> None:
        self._entries: dict[str, PresenceInfo] = {}
        self._idle_timeout = idle_timeout_s

    def update(self, component_id: str, state: PresenceState) -> None:
        if component_id not in self._entries:
            self._entries[component_id] = PresenceInfo(component_id=component_id)
        self._entries[component_id].state = state
        self._entries[component_id].last_seen_at = time.time()

    def heartbeat(self, component_id: str) -> None:
        """Record a heartbeat (marks online and updates last_seen)."""
        self.update(component_id, PresenceState.ONLINE)

    def get(self, component_id: str) -> PresenceInfo | None:
        return self._entries.get(component_id)

    def check_idle(self) -> list[str]:
        """Find components that have gone idle (no heartbeat within timeout)."""
        now = time.time()
        idle: list[str] = []
        for cid, info in self._entries.items():
            if info.state == PresenceState.ONLINE:
                if now - info.last_seen_at > self._idle_timeout:
                    info.state = PresenceState.IDLE
                    idle.append(cid)
        return idle

    def all_online(self) -> list[str]:
        return [cid for cid, info in self._entries.items() if info.state == PresenceState.ONLINE]

    @property
    def component_count(self) -> int:
        return len(self._entries)


# ---------------------------------------------------------------------------
# Wake Manager
# ---------------------------------------------------------------------------

class WakeManager:
    """Handle sleep/wake transitions."""

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._last_wake: float = 0.0
        self._sleep_at: float = 0.0
        self._wake_count: int = 0

    def on_sleep(self) -> None:
        self._sleep_at = time.time()
        self._bus.emit(SystemEvent(
            event_type=EventType.SYSTEM_SLEEP,
            source="wake-manager",
        ))

    def on_wake(self) -> None:
        self._last_wake = time.time()
        self._wake_count += 1
        sleep_duration = (self._last_wake - self._sleep_at) if self._sleep_at else 0
        self._bus.emit(SystemEvent(
            event_type=EventType.SYSTEM_WAKE,
            source="wake-manager",
            data={"sleep_duration_s": sleep_duration, "wake_count": self._wake_count},
        ))

    @property
    def last_wake(self) -> float:
        return self._last_wake

    @property
    def wake_count(self) -> int:
        return self._wake_count
