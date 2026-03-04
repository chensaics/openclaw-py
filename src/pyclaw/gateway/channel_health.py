"""Channel health monitor — periodic checks, cooldown, max restarts.

Ported from ``src/gateway/channel-health-monitor.ts``.

Provides:
- Periodic channel health checking
- Cooldown periods between checks
- Max restart limits per hour
- Channel restart triggers
- Health history tracking
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckConfig:
    """Configuration for channel health monitoring."""

    check_interval_s: float = 60.0
    cooldown_s: float = 300.0
    max_restarts_per_hour: int = 3
    unhealthy_threshold: int = 3
    degraded_threshold: int = 2
    enabled: bool = True


@dataclass
class ChannelHealthState:
    """Health state for a single channel."""

    channel_id: str
    status: HealthStatus = HealthStatus.UNKNOWN
    consecutive_failures: int = 0
    last_check_at: float = 0.0
    last_healthy_at: float = 0.0
    last_restart_at: float = 0.0
    restart_count_hour: int = 0
    restart_hour_start: float = 0.0
    error_message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthCheckResult:
    """Result from a single health check."""

    channel_id: str
    healthy: bool
    latency_ms: float = 0.0
    error: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RestartDecision:
    """Whether a channel should be restarted."""

    should_restart: bool
    reason: str = ""
    cooldown_remaining_s: float = 0.0


class ChannelHealthMonitor:
    """Monitor health of all registered channels."""

    def __init__(self, config: HealthCheckConfig | None = None) -> None:
        self._config = config or HealthCheckConfig()
        self._states: dict[str, ChannelHealthState] = {}
        self._history: dict[str, list[HealthCheckResult]] = {}
        self._max_history = 50

    def register_channel(self, channel_id: str) -> None:
        if channel_id not in self._states:
            self._states[channel_id] = ChannelHealthState(channel_id=channel_id)
            self._history[channel_id] = []

    def unregister_channel(self, channel_id: str) -> None:
        self._states.pop(channel_id, None)
        self._history.pop(channel_id, None)

    def record_check(self, result: HealthCheckResult) -> HealthStatus:
        """Record a health check result and update state."""
        state = self._states.get(result.channel_id)
        if not state:
            self.register_channel(result.channel_id)
            state = self._states[result.channel_id]

        state.last_check_at = time.time()
        history = self._history.setdefault(result.channel_id, [])
        history.append(result)
        if len(history) > self._max_history:
            history.pop(0)

        if result.healthy:
            state.consecutive_failures = 0
            state.last_healthy_at = time.time()
            state.status = HealthStatus.HEALTHY
            state.error_message = ""
        else:
            state.consecutive_failures += 1
            state.error_message = result.error

            if state.consecutive_failures >= self._config.unhealthy_threshold:
                state.status = HealthStatus.UNHEALTHY
            elif state.consecutive_failures >= self._config.degraded_threshold:
                state.status = HealthStatus.DEGRADED

        return state.status

    def should_restart(self, channel_id: str) -> RestartDecision:
        """Determine if a channel should be restarted."""
        state = self._states.get(channel_id)
        if not state:
            return RestartDecision(should_restart=False, reason="Channel not registered")

        if state.status != HealthStatus.UNHEALTHY:
            return RestartDecision(should_restart=False, reason="Channel is not unhealthy")

        now = time.time()

        # Cooldown check
        if state.last_restart_at > 0:
            elapsed = now - state.last_restart_at
            if elapsed < self._config.cooldown_s:
                return RestartDecision(
                    should_restart=False,
                    reason="In cooldown period",
                    cooldown_remaining_s=self._config.cooldown_s - elapsed,
                )

        # Hourly restart limit
        if now - state.restart_hour_start > 3600:
            state.restart_count_hour = 0
            state.restart_hour_start = now

        if state.restart_count_hour >= self._config.max_restarts_per_hour:
            return RestartDecision(
                should_restart=False,
                reason=f"Max restarts ({self._config.max_restarts_per_hour}/hour) exceeded",
            )

        return RestartDecision(should_restart=True, reason="Channel unhealthy, restart allowed")

    def record_restart(self, channel_id: str) -> None:
        """Record that a channel was restarted."""
        state = self._states.get(channel_id)
        if state:
            now = time.time()
            state.last_restart_at = now
            state.restart_count_hour += 1
            state.consecutive_failures = 0
            state.status = HealthStatus.UNKNOWN

    def needs_check(self, channel_id: str) -> bool:
        """Whether a channel is due for a health check."""
        state = self._states.get(channel_id)
        if not state:
            return True
        if state.last_check_at == 0:
            return True
        return time.time() - state.last_check_at >= self._config.check_interval_s

    def get_status(self, channel_id: str) -> HealthStatus:
        state = self._states.get(channel_id)
        return state.status if state else HealthStatus.UNKNOWN

    def get_all_statuses(self) -> dict[str, HealthStatus]:
        return {cid: s.status for cid, s in self._states.items()}

    def get_unhealthy_channels(self) -> list[str]:
        return [cid for cid, s in self._states.items() if s.status == HealthStatus.UNHEALTHY]

    def get_state(self, channel_id: str) -> ChannelHealthState | None:
        return self._states.get(channel_id)

    def get_history(self, channel_id: str, limit: int = 10) -> list[HealthCheckResult]:
        history = self._history.get(channel_id, [])
        return history[-limit:]

    @property
    def channel_count(self) -> int:
        return len(self._states)
