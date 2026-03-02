"""Reply dispatcher — config-based dispatch, origin routing, deduplication.

Ported from ``src/auto-reply/reply/reply-dispatcher.ts``.

Provides:
- Reply dispatcher with lifecycle (start/stop)
- Config-based dispatch (route messages to agents)
- Origin routing (route based on message source)
- Inbound deduplication (prevent duplicate processing)
- Dispatcher registry (track active dispatchers)
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


@dataclass
class InboundMessage:
    """An inbound message to be dispatched."""
    text: str
    sender_id: str
    channel_id: str
    channel_type: str = ""    # "dm" | "group"
    session_id: str = ""
    message_id: str = ""
    timestamp: float = 0.0
    is_command: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()


@dataclass
class DispatchResult:
    """Result of dispatching a message."""
    dispatched: bool = True
    reply_text: str = ""
    error: str = ""
    deduplicated: bool = False
    routed_to: str = ""       # Agent or handler


ReplyHandler = Callable[[InboundMessage], Coroutine[Any, Any, DispatchResult]]


@dataclass
class DispatchRoute:
    """A dispatch route mapping."""
    name: str
    handler: ReplyHandler
    priority: int = 0
    channel_filter: str = ""     # Empty = all channels
    sender_filter: str = ""      # Empty = all senders


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

class InboundDeduplicator:
    """Prevent processing the same message twice.

    Uses a bounded LRU cache of message fingerprints.
    """

    def __init__(self, *, max_size: int = 500, ttl_s: float = 300.0) -> None:
        self._max_size = max_size
        self._ttl_s = ttl_s
        self._seen: OrderedDict[str, float] = OrderedDict()

    def _fingerprint(self, msg: InboundMessage) -> str:
        raw = f"{msg.channel_id}:{msg.sender_id}:{msg.text}:{msg.message_id}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def is_duplicate(self, msg: InboundMessage) -> bool:
        fp = self._fingerprint(msg)
        now = time.time()

        # Prune expired
        expired = [k for k, t in self._seen.items() if now - t > self._ttl_s]
        for k in expired:
            del self._seen[k]

        if fp in self._seen:
            return True

        self._seen[fp] = now
        # Evict oldest if over capacity
        while len(self._seen) > self._max_size:
            self._seen.popitem(last=False)

        return False

    def clear(self) -> None:
        self._seen.clear()


# ---------------------------------------------------------------------------
# Reply Dispatcher
# ---------------------------------------------------------------------------

class ReplyDispatcher:
    """Dispatch inbound messages to handlers via routes."""

    def __init__(self, *, dedup_ttl_s: float = 300.0) -> None:
        self._routes: list[DispatchRoute] = []
        self._dedup = InboundDeduplicator(ttl_s=dedup_ttl_s)
        self._running = False
        self._dispatch_count = 0

    def add_route(self, route: DispatchRoute) -> None:
        self._routes.append(route)
        self._routes.sort(key=lambda r: r.priority, reverse=True)

    def remove_route(self, name: str) -> bool:
        before = len(self._routes)
        self._routes = [r for r in self._routes if r.name != name]
        return len(self._routes) < before

    async def dispatch(self, message: InboundMessage) -> DispatchResult:
        """Dispatch an inbound message to the first matching route."""
        if self._dedup.is_duplicate(message):
            return DispatchResult(dispatched=False, deduplicated=True)

        for route in self._routes:
            if route.channel_filter and route.channel_filter != message.channel_id:
                continue
            if route.sender_filter and route.sender_filter != message.sender_id:
                continue

            try:
                result = await route.handler(message)
                self._dispatch_count += 1
                result.routed_to = route.name
                return result
            except Exception as e:
                logger.error("Dispatch error in route '%s': %s", route.name, e)
                return DispatchResult(dispatched=False, error=str(e))

        return DispatchResult(dispatched=False, error="No matching route")

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def dispatch_count(self) -> int:
        return self._dispatch_count

    @property
    def route_count(self) -> int:
        return len(self._routes)


# ---------------------------------------------------------------------------
# Dispatcher Registry
# ---------------------------------------------------------------------------

class DispatcherRegistry:
    """Track active dispatchers."""

    def __init__(self) -> None:
        self._dispatchers: dict[str, ReplyDispatcher] = {}

    def register(self, name: str, dispatcher: ReplyDispatcher) -> None:
        self._dispatchers[name] = dispatcher

    def unregister(self, name: str) -> bool:
        return self._dispatchers.pop(name, None) is not None

    def get(self, name: str) -> ReplyDispatcher | None:
        return self._dispatchers.get(name)

    def list_active(self) -> list[str]:
        return [n for n, d in self._dispatchers.items() if d.is_running]

    def stop_all(self) -> None:
        for d in self._dispatchers.values():
            d.stop()
