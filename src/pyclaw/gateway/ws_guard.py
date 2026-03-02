"""WebSocket flood guard — unauthenticated connection rate limiting and flood detection.

Ported from ``src/gateway/`` WebSocket flood-protection logic.

Provides:
- Per-IP connection rate limiting with sliding window
- Unauthenticated flood detection (rapid connect/disconnect)
- Sampled logging to avoid log-spam under attack
- Hard cap on total tracked IPs to bound memory
- Auto-ban with configurable cooldown
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_S = 60.0
DEFAULT_MAX_CONNECTIONS_PER_WINDOW = 30
DEFAULT_MAX_TRACKED_IPS = 50000
DEFAULT_BAN_DURATION_S = 300.0
DEFAULT_SAMPLE_INTERVAL = 10  # log every Nth blocked attempt


@dataclass
class WsGuardConfig:
    """Configuration for WebSocket flood guard."""

    window_s: float = DEFAULT_WINDOW_S
    max_connections_per_window: int = DEFAULT_MAX_CONNECTIONS_PER_WINDOW
    max_tracked_ips: int = DEFAULT_MAX_TRACKED_IPS
    ban_duration_s: float = DEFAULT_BAN_DURATION_S
    sample_interval: int = DEFAULT_SAMPLE_INTERVAL
    enabled: bool = True


@dataclass
class _IpBucket:
    """Tracking state for a single IP address."""

    timestamps: list[float] = field(default_factory=list)
    banned_until: float = 0.0
    blocked_count: int = 0
    first_seen: float = 0.0

    def __post_init__(self) -> None:
        if self.first_seen == 0.0:
            self.first_seen = time.time()


@dataclass
class FloodEvent:
    """A detected flood event for auditing."""

    ip: str
    connection_count: int
    window_s: float
    action: str  # "rate_limited" | "banned"
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class WsFloodGuard:
    """WebSocket flood guard with per-IP rate limiting and auto-ban."""

    def __init__(self, config: WsGuardConfig | None = None) -> None:
        self._config = config or WsGuardConfig()
        self._buckets: dict[str, _IpBucket] = {}
        self._events: list[FloodEvent] = []
        self._max_events = 500
        self._total_blocked = 0
        self._log_counter = 0

    def check_connection(self, ip: str) -> bool:
        """Check if a new WebSocket connection from this IP is allowed.

        Returns True if allowed, False if rate-limited or banned.
        """
        if not self._config.enabled:
            return True

        now = time.time()
        self._maybe_prune(now)

        bucket = self._buckets.get(ip)

        if bucket is None:
            if len(self._buckets) >= self._config.max_tracked_ips:
                # Hard cap — reject unknown IPs under pressure
                self._record_blocked(ip, 0, "ip_cap_exceeded")
                return False
            bucket = _IpBucket()
            self._buckets[ip] = bucket

        # Check ban
        if bucket.banned_until > now:
            self._record_blocked(ip, len(bucket.timestamps), "banned")
            return False

        # Prune old timestamps
        cutoff = now - self._config.window_s
        bucket.timestamps = [t for t in bucket.timestamps if t > cutoff]

        # Check rate
        if len(bucket.timestamps) >= self._config.max_connections_per_window:
            bucket.banned_until = now + self._config.ban_duration_s
            self._record_flood(ip, len(bucket.timestamps), "banned")
            self._record_blocked(ip, len(bucket.timestamps), "rate_limited")
            return False

        bucket.timestamps.append(now)
        return True

    def is_banned(self, ip: str) -> bool:
        """Check if an IP is currently banned."""
        bucket = self._buckets.get(ip)
        if bucket is None:
            return False
        return bucket.banned_until > time.time()

    def unban(self, ip: str) -> None:
        """Manually unban an IP."""
        bucket = self._buckets.get(ip)
        if bucket:
            bucket.banned_until = 0.0

    def get_stats(self) -> dict[str, Any]:
        """Get guard statistics."""
        now = time.time()
        banned_count = sum(1 for b in self._buckets.values() if b.banned_until > now)
        return {
            "tracked_ips": len(self._buckets),
            "banned_ips": banned_count,
            "total_blocked": self._total_blocked,
            "recent_events": len(self._events),
        }

    def get_recent_events(self, *, limit: int = 50) -> list[FloodEvent]:
        return self._events[-limit:]

    def reset(self) -> None:
        """Reset all tracking state."""
        self._buckets.clear()
        self._events.clear()
        self._total_blocked = 0

    def _record_flood(self, ip: str, count: int, action: str) -> None:
        """Record a flood event."""
        event = FloodEvent(
            ip=ip,
            connection_count=count,
            window_s=self._config.window_s,
            action=action,
        )
        if len(self._events) >= self._max_events:
            self._events = self._events[-self._max_events // 2 :]
        self._events.append(event)

    def _record_blocked(self, ip: str, count: int, reason: str) -> None:
        """Record a blocked attempt with sampled logging."""
        self._total_blocked += 1
        bucket = self._buckets.get(ip)
        if bucket:
            bucket.blocked_count += 1

        self._log_counter += 1
        if self._log_counter % self._config.sample_interval == 1:
            logger.warning(
                "WS flood guard blocked connection: ip=%s reason=%s count=%d total_blocked=%d",
                ip, reason, count, self._total_blocked,
            )

    def _maybe_prune(self, now: float) -> None:
        """Prune stale buckets when count exceeds half of max."""
        if len(self._buckets) < self._config.max_tracked_ips // 2:
            return

        stale_cutoff = now - self._config.window_s * 3
        stale_keys = [
            k for k, v in self._buckets.items()
            if v.banned_until < now and (not v.timestamps or v.timestamps[-1] < stale_cutoff)
        ]
        for k in stale_keys:
            del self._buckets[k]
