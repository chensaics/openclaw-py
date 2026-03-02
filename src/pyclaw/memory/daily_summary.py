"""Daily summary service — automated session consolidation.

Periodically scans sessions from the previous day, extracts highlights,
and writes a summary into the memory store.  Designed to run as a
background service alongside the Gateway.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DaySummaryData:
    """Aggregated data for a single day."""

    date: str  # YYYY-MM-DD
    session_keys: list[str] = field(default_factory=list)
    user_messages: list[str] = field(default_factory=list)
    assistant_messages: list[str] = field(default_factory=list)
    total_messages: int = 0


@dataclass
class DailySummaryConfig:
    interval_hours: float = 1.0
    max_highlights: int = 5
    highlight_max_len: int = 180


class DailySummaryService:
    """Collects and persists daily session summaries."""

    def __init__(
        self,
        sessions_dir: Path,
        *,
        config: DailySummaryConfig | None = None,
        memory_store: Any = None,
    ) -> None:
        self._sessions_dir = sessions_dir
        self._config = config or DailySummaryConfig()
        self._memory_store = memory_store
        self._generated_dates: set[str] = set()
        self._running = False

    async def start(self) -> None:
        """Start the background summary loop."""
        import asyncio

        self._running = True
        logger.info("DailySummaryService started (interval=%.1fh)", self._config.interval_hours)

        while self._running:
            try:
                self._generate_yesterday_summary()
            except Exception:
                logger.exception("Daily summary generation failed")
            await asyncio.sleep(self._config.interval_hours * 3600)

    def stop(self) -> None:
        self._running = False

    def generate_now(self, target_date: str | None = None) -> DaySummaryData | None:
        """Manually trigger summary generation. Returns the summary data or None."""
        if target_date:
            return self._generate_for_date(target_date)
        return self._generate_yesterday_summary()

    def _generate_yesterday_summary(self) -> DaySummaryData | None:
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        return self._generate_for_date(yesterday)

    def _generate_for_date(self, date_str: str) -> DaySummaryData | None:
        if date_str in self._generated_dates:
            logger.debug("Summary already generated for %s", date_str)
            return None

        data = self._collect_sessions_for_date(date_str)
        if not data.session_keys:
            logger.debug("No sessions found for %s", date_str)
            return None

        summary_text = self._build_summary_text(data)
        self._persist_summary(data, summary_text)
        self._generated_dates.add(date_str)
        logger.info("Generated daily summary for %s (%d sessions)", date_str, len(data.session_keys))
        return data

    def _collect_sessions_for_date(self, date_str: str) -> DaySummaryData:
        data = DaySummaryData(date=date_str)

        if not self._sessions_dir.exists():
            return data

        for session_file in self._sessions_dir.glob("**/*.jsonl"):
            found_messages = False
            try:
                with open(session_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        if entry.get("type") != "message":
                            continue

                        msg = entry.get("message", {})
                        role = msg.get("role", "")
                        content = msg.get("content", "")
                        if not isinstance(content, str):
                            continue

                        ts = entry.get("timestamp", 0)
                        if ts:
                            entry_date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                        else:
                            entry_date = _guess_date_from_file(session_file)

                        if entry_date != date_str:
                            continue

                        found_messages = True
                        data.total_messages += 1
                        if role == "user":
                            data.user_messages.append(content)
                        elif role == "assistant":
                            data.assistant_messages.append(content)

            except Exception:
                logger.debug("Error reading session file %s", session_file)

            if found_messages:
                data.session_keys.append(session_file.stem)

        return data

    def _build_summary_text(self, data: DaySummaryData) -> str:
        cfg = self._config
        lines = [f"### {data.date}"]
        lines.append(f"- Sessions active: {len(data.session_keys)}")
        lines.append(f"- Messages: {data.total_messages}")

        user_highlights = _unique_top_n(data.user_messages, cfg.max_highlights, cfg.highlight_max_len)
        if user_highlights:
            lines.append("- User highlights:")
            for h in user_highlights:
                lines.append(f"  - {h}")

        assistant_highlights = _unique_top_n(data.assistant_messages, cfg.max_highlights, cfg.highlight_max_len)
        if assistant_highlights:
            lines.append("- Assistant highlights:")
            for h in assistant_highlights:
                lines.append(f"  - {h}")

        return "\n".join(lines)

    def _persist_summary(self, data: DaySummaryData, text: str) -> None:
        if self._memory_store:
            try:
                self._memory_store.add(
                    text,
                    source="daily_summary",
                    tags=["daily_summary", data.date],
                    metadata={"date": data.date, "sessions": len(data.session_keys)},
                )
            except Exception:
                logger.warning("Failed to persist summary to memory store")

        self._write_summary_markdown(data, text)

    def _write_summary_markdown(self, data: DaySummaryData, text: str) -> None:
        if not self._sessions_dir.parent.exists():
            return

        summary_dir = self._sessions_dir.parent / "summaries"
        summary_dir.mkdir(parents=True, exist_ok=True)
        path = summary_dir / f"summary_{data.date}.md"

        if path.exists():
            return

        path.write_text(text + "\n", encoding="utf-8")


def _unique_top_n(messages: list[str], n: int, max_len: int) -> list[str]:
    """Extract the top-N unique, longest messages (truncated)."""
    seen: set[str] = set()
    result: list[str] = []
    sorted_msgs = sorted(messages, key=len, reverse=True)
    for msg in sorted_msgs:
        normalized = msg.strip()[:max_len]
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
            if len(result) >= n:
                break
    return result


def _guess_date_from_file(path: Path) -> str:
    """Guess date from file modification time when entries lack timestamps."""
    try:
        mtime = path.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return ""
