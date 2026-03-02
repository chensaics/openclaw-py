"""Tests for enhanced pyclaw.cron.scheduler — every/once/at scheduling."""

from datetime import datetime, timedelta, timezone

import pytest

from pyclaw.cron.scheduler import CronJob, ScheduleType, parse_at_time


class TestCronJobSerialization:
    def test_to_dict(self) -> None:
        job = CronJob(
            id="j1",
            name="Test Job",
            schedule="0 9 * * *",
            schedule_type=ScheduleType.CRON,
            channel="telegram",
            deliver=True,
        )
        d = job.to_dict()
        assert d["id"] == "j1"
        assert d["scheduleType"] == "cron"
        assert d["deliver"] is True

    def test_from_dict(self) -> None:
        data = {
            "id": "j2",
            "name": "Interval Job",
            "schedule": "",
            "scheduleType": "every",
            "everySeconds": 300,
            "message": "check status",
        }
        job = CronJob.from_dict(data)
        assert job.schedule_type == ScheduleType.EVERY
        assert job.every_seconds == 300.0

    def test_once_type(self) -> None:
        data = {
            "id": "j3",
            "name": "One-time",
            "schedule": "",
            "scheduleType": "once",
            "at": "2026-12-31 23:59",
        }
        job = CronJob.from_dict(data)
        assert job.schedule_type == ScheduleType.ONCE
        assert job.at == "2026-12-31 23:59"


class TestParseAtTime:
    def test_iso_8601(self) -> None:
        dt = parse_at_time("2026-03-02T14:30:00")
        assert dt is not None
        assert dt.hour == 14
        assert dt.minute == 30

    def test_date_time(self) -> None:
        dt = parse_at_time("2026-03-02 14:30")
        assert dt is not None
        assert dt.year == 2026

    def test_time_only(self) -> None:
        dt = parse_at_time("09:30")
        assert dt is not None
        assert dt.hour == 9
        assert dt.minute == 30
        assert dt > datetime.now(timezone.utc)

    def test_time_only_tomorrow(self) -> None:
        now = datetime.now(timezone.utc)
        past_time = f"{now.hour:02d}:{now.minute:02d}"
        dt = parse_at_time(past_time)
        if dt is not None:
            assert dt >= now

    def test_invalid(self) -> None:
        assert parse_at_time("") is None
        assert parse_at_time("not-a-date") is None

    def test_whitespace(self) -> None:
        dt = parse_at_time("  2026-03-02T10:00  ")
        assert dt is not None


class TestScheduleType:
    def test_enum_values(self) -> None:
        assert ScheduleType.CRON.value == "cron"
        assert ScheduleType.EVERY.value == "every"
        assert ScheduleType.ONCE.value == "once"
