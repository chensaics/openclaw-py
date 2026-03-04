"""Heartbeat runner — periodic agent check-ins.

Ported from ``src/infra/heartbeat-runner.ts``.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DURATION_PATTERN = re.compile(r"^(\d+)(ms|s|m|h|d)$")
COMPOUND_PATTERN = re.compile(
    r"^(?:(?P<hours>\d+)h)?(?:(?P<minutes>\d+)m)?(?:(?P<seconds>\d+)s)?$",
    re.IGNORECASE,
)


def parse_duration_ms(value: str) -> int:
    """Parse a duration string to milliseconds.

    Supports both simple ('30m', '2h') and compound ('2h30m', '1h15m30s') formats.
    """
    value = value.strip()
    if not value:
        return 30 * 60 * 1000

    # Try simple format first
    m = DURATION_PATTERN.match(value)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        multipliers = {"ms": 1, "s": 1000, "m": 60_000, "h": 3_600_000, "d": 86_400_000}
        return n * multipliers[unit]

    # Try compound format (e.g. "2h30m", "1h15m30s")
    cm = COMPOUND_PATTERN.match(value)
    if cm and any(cm.group(g) for g in ("hours", "minutes", "seconds")):
        hours = int(cm.group("hours") or 0)
        minutes = int(cm.group("minutes") or 0)
        seconds = int(cm.group("seconds") or 0)
        total = hours * 3_600_000 + minutes * 60_000 + seconds * 1000
        if total > 0:
            return total

    logger.warning("Invalid duration '%s', using default 30m", value)
    return 30 * 60 * 1000


def resolve_heartbeat_query(
    config: HeartbeatConfig,
    workspace_root: Path | None = None,
) -> str:
    """Resolve the heartbeat prompt, reading from HEARTBEAT.md if configured."""
    if config.query_file:
        query_path = Path(config.query_file)
        if not query_path.is_absolute() and workspace_root:
            query_path = workspace_root / query_path
        if query_path.is_file():
            text = query_path.read_text(encoding="utf-8").strip()
            if text:
                return text
            logger.debug("HEARTBEAT.md exists but is empty, using default prompt")

    return config.prompt or "Check in — anything to report?"


@dataclass
class HeartbeatConfig:
    every: str = "30m"
    prompt: str = ""
    query_file: str = ""  # e.g. "HEARTBEAT.md" — overrides prompt if file exists
    target: str = ""  # "" | "last" — dispatch to last active channel
    account_id: str = ""
    active_hours: str = ""  # e.g. "09:00-22:00"
    enabled: bool = True


@dataclass
class HeartbeatSummary:
    agent_id: str
    last_run: float = 0.0
    last_text: str = ""
    next_due: float = 0.0
    runs: int = 0


WakeReason = str  # "exec" | "cron" | "wake" | "regular"


def is_within_active_hours(config: HeartbeatConfig, now: float | None = None) -> bool:
    """Check if current time is within configured active hours window."""
    if not config.active_hours:
        return True

    parts = config.active_hours.split("-")
    if len(parts) != 2:
        return True

    try:
        start_h, start_m = map(int, parts[0].strip().split(":"))
        end_h, end_m = map(int, parts[1].strip().split(":"))
    except (ValueError, IndexError):
        return True

    import datetime

    dt = datetime.datetime.fromtimestamp(now or time.time())
    current_minutes = dt.hour * 60 + dt.minute
    start_minutes = start_h * 60 + start_m
    end_minutes = end_h * 60 + end_m

    if start_minutes <= end_minutes:
        return start_minutes <= current_minutes <= end_minutes
    # wraps midnight
    return current_minutes >= start_minutes or current_minutes <= end_minutes


def resolve_heartbeat_interval_ms(config: HeartbeatConfig) -> int:
    return parse_duration_ms(config.every)


ReplyFn = Callable[[str, str], Awaitable[str | None]]
DispatchFn = Callable[[str, str], Awaitable[None]]


class HeartbeatRunner:
    """Manages periodic heartbeats for one or more agents."""

    def __init__(self, *, workspace_root: Path | None = None) -> None:
        self._summaries: dict[str, HeartbeatSummary] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._wake_handlers: dict[str, Callable[[], None]] = {}
        self._running = False
        self._workspace_root = workspace_root
        self._dispatch_fn: DispatchFn | None = None
        self._last_channel: str = ""

    def set_dispatch(self, dispatch_fn: DispatchFn) -> None:
        """Set a function to dispatch replies to channels."""
        self._dispatch_fn = dispatch_fn

    def record_channel_activity(self, channel_id: str) -> None:
        """Record which channel was last active (for target=last)."""
        self._last_channel = channel_id

    def start(
        self,
        agent_id: str,
        config: HeartbeatConfig,
        reply_fn: ReplyFn,
    ) -> None:
        if agent_id in self._tasks:
            return
        summary = HeartbeatSummary(agent_id=agent_id)
        self._summaries[agent_id] = summary
        self._running = True
        task = asyncio.ensure_future(self._loop(agent_id, config, reply_fn, summary))
        self._tasks[agent_id] = task

    def stop(self, agent_id: str | None = None) -> None:
        if agent_id:
            task = self._tasks.pop(agent_id, None)
            if task:
                task.cancel()
            self._summaries.pop(agent_id, None)
        else:
            self._running = False
            for task in self._tasks.values():
                task.cancel()
            self._tasks.clear()
            self._summaries.clear()

    def request_now(self, agent_id: str, reason: WakeReason = "wake") -> None:
        """Request an immediate heartbeat for *agent_id*."""
        summary = self._summaries.get(agent_id)
        if summary:
            summary.next_due = 0.0
        handler = self._wake_handlers.get(agent_id)
        if handler:
            handler()

    def get_summary(self, agent_id: str) -> HeartbeatSummary | None:
        return self._summaries.get(agent_id)

    async def _loop(
        self,
        agent_id: str,
        config: HeartbeatConfig,
        reply_fn: ReplyFn,
        summary: HeartbeatSummary,
    ) -> None:
        interval_s = resolve_heartbeat_interval_ms(config) / 1000.0
        wake_event = asyncio.Event()
        self._wake_handlers[agent_id] = wake_event.set

        while self._running:
            try:
                now = time.time()
                if summary.next_due > now:
                    wait = summary.next_due - now
                    try:
                        await asyncio.wait_for(wake_event.wait(), timeout=wait)
                        wake_event.clear()
                    except TimeoutError:
                        pass

                if not self._running:
                    break

                if not config.enabled:
                    summary.next_due = time.time() + interval_s
                    continue

                if not is_within_active_hours(config):
                    summary.next_due = time.time() + 60.0
                    continue

                await self._run_once(agent_id, config, reply_fn, summary)
                summary.next_due = time.time() + interval_s
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Heartbeat error for %s", agent_id)
                summary.next_due = time.time() + interval_s

        self._wake_handlers.pop(agent_id, None)

    async def _run_once(
        self,
        agent_id: str,
        config: HeartbeatConfig,
        reply_fn: ReplyFn,
        summary: HeartbeatSummary,
    ) -> None:
        prompt = resolve_heartbeat_query(config, self._workspace_root)
        try:
            reply = await reply_fn(agent_id, prompt)
            summary.last_run = time.time()
            summary.runs += 1
            if reply and reply != summary.last_text:
                summary.last_text = reply
                logger.info("Heartbeat[%s]: %s", agent_id, reply[:100])

                # Dispatch to last active channel if configured
                if config.target.lower() == "last" and self._last_channel and self._dispatch_fn:
                    try:
                        await self._dispatch_fn(self._last_channel, reply)
                        logger.info(
                            "Heartbeat[%s] dispatched to channel %s",
                            agent_id,
                            self._last_channel,
                        )
                    except Exception:
                        logger.exception(
                            "Heartbeat dispatch failed for %s",
                            agent_id,
                        )
        except Exception:
            logger.exception("Heartbeat reply error for %s", agent_id)
