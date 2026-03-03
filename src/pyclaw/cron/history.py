"""Cron execution history — persistent record of scheduled task runs.

Tracks execution records with start/end times, status, output, errors,
and duration.  Supports both in-memory and SQLite persistence.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


@dataclass
class ExecutionRecord:
    """A single cron job execution record."""

    id: str
    job_id: str
    job_title: str = ""
    status: ExecutionStatus = ExecutionStatus.PENDING
    started_at: float = 0.0
    ended_at: float = 0.0
    output: str = ""
    error: str = ""

    @property
    def duration_s(self) -> float:
        if not self.started_at:
            return 0.0
        end = self.ended_at or time.time()
        return end - self.started_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "jobId": self.job_id,
            "jobTitle": self.job_title,
            "status": self.status.value,
            "startedAt": self.started_at,
            "endedAt": self.ended_at,
            "output": self.output,
            "error": self.error,
            "durationS": round(self.duration_s, 3),
        }


class HistoryStore:
    """In-memory execution history with optional JSON persistence."""

    def __init__(self, *, max_size: int = 1000, persist_path: Path | None = None) -> None:
        self._records: list[ExecutionRecord] = []
        self._max_size = max_size
        self._persist_path = persist_path
        if persist_path:
            self._load()

    def add(self, record: ExecutionRecord) -> None:
        self._records.append(record)
        if len(self._records) > self._max_size:
            self._records = self._records[-self._max_size:]
        self._save()

    def update(self, record_id: str, **kwargs: Any) -> ExecutionRecord | None:
        """Update fields on an existing record."""
        for rec in reversed(self._records):
            if rec.id == record_id:
                for k, v in kwargs.items():
                    if hasattr(rec, k):
                        setattr(rec, k, v)
                self._save()
                return rec
        return None

    def get(self, record_id: str) -> ExecutionRecord | None:
        for rec in reversed(self._records):
            if rec.id == record_id:
                return rec
        return None

    def list_for_job(self, job_id: str, *, limit: int = 50) -> list[ExecutionRecord]:
        result = [r for r in reversed(self._records) if r.job_id == job_id]
        return result[:limit]

    def list_recent(self, *, limit: int = 50) -> list[ExecutionRecord]:
        return list(reversed(self._records[-limit:]))

    def clear(self) -> None:
        self._records.clear()
        self._save()

    @property
    def count(self) -> int:
        return len(self._records)

    def _save(self) -> None:
        if not self._persist_path:
            return
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            data = [r.to_dict() for r in self._records[-self._max_size:]]
            self._persist_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            logger.debug("Failed to persist cron history")

    def _load(self) -> None:
        if not self._persist_path or not self._persist_path.exists():
            return
        try:
            raw = json.loads(self._persist_path.read_text(encoding="utf-8"))
            records_source: list[dict[str, Any]] = []
            if isinstance(raw, dict):
                jobs = raw.get("jobs", [])
                migrated = 0
                for job in jobs:
                    if not isinstance(job, dict):
                        continue
                    changed = False
                    if "command" in job and "handler_id" not in job and "handlerId" not in job:
                        job["handlerId"] = job.pop("command")
                        changed = True
                    schedule = job.get("schedule", "")
                    if isinstance(schedule, str) and schedule and len(schedule.split()) != 5:
                        try:
                            job["schedule"] = _legacy_schedule_to_cron(schedule)
                            changed = True
                        except ValueError:
                            pass
                    if changed:
                        migrated += 1
                if migrated:
                    logger.info("Migrated %d legacy cron job(s)", migrated)
                records_source = raw.get("executions", raw.get("history", []))
            else:
                records_source = raw if isinstance(raw, list) else []
            for item in records_source:
                if not isinstance(item, dict) or not item.get("id"):
                    continue
                self._records.append(
                    ExecutionRecord(
                        id=item.get("id", ""),
                        job_id=item.get("jobId", ""),
                        job_title=item.get("jobTitle", ""),
                        status=ExecutionStatus(item.get("status", "completed")),
                        started_at=item.get("startedAt", 0.0),
                        ended_at=item.get("endedAt", 0.0),
                        output=item.get("output", ""),
                        error=item.get("error", ""),
                    )
                )
        except Exception:
            logger.debug("Failed to load cron history")


def _legacy_schedule_to_cron(s: str) -> str:
    """Convert legacy schedule string to cron expression."""
    s = (s or "").strip().lower()
    if not s:
        return "0 0 * * *"
    if s in ("daily", "day"):
        return "0 0 * * *"
    if s in ("hourly", "hour"):
        return "0 * * * *"
    if s.startswith("every ") and "second" in s:
        return "*/1 * * * *"
    if s.startswith("every ") and "minute" in s:
        return "*/1 * * * *"
    raise ValueError(f"Cannot convert legacy schedule: {s}")
