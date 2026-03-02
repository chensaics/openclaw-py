"""Heartbeat runner — periodic agent check-ins.

Ported from ``src/infra/heartbeat-runner.ts``.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

DURATION_PATTERN = re.compile(r"^(\d+)(ms|s|m|h|d)$")


def parse_duration_ms(value: str) -> int:
    """Parse a duration string (e.g. '30m', '2h') to milliseconds."""
    m = DURATION_PATTERN.match(value.strip())
    if not m:
        return 30 * 60 * 1000  # default 30m
    n, unit = int(m.group(1)), m.group(2)
    multipliers = {"ms": 1, "s": 1000, "m": 60_000, "h": 3_600_000, "d": 86_400_000}
    return n * multipliers[unit]


@dataclass
class HeartbeatConfig:
    every: str = "30m"
    prompt: str = ""
    target: str = ""
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


class HeartbeatRunner:
    """Manages periodic heartbeats for one or more agents."""

    def __init__(self) -> None:
        self._summaries: dict[str, HeartbeatSummary] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._wake_handlers: dict[str, Callable[[], None]] = {}
        self._running = False

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
                    except asyncio.TimeoutError:
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
        prompt = config.prompt or "Check in — anything to report?"
        try:
            reply = await reply_fn(agent_id, prompt)
            summary.last_run = time.time()
            summary.runs += 1
            if reply:
                # dedupe against last heartbeat text
                if reply != summary.last_text:
                    summary.last_text = reply
                    logger.info("Heartbeat[%s]: %s", agent_id, reply[:100])
        except Exception:
            logger.exception("Heartbeat reply error for %s", agent_id)
