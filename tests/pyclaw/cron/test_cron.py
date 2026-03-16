"""Tests for cron scheduler."""

from pyclaw.cron.scheduler import CronJob, CronScheduler


def test_cron_job_to_dict():
    job = CronJob(
        id="daily-summary",
        name="Daily Summary",
        schedule="0 9 * * *",
        agent_id="main",
        message="Give me a summary of today's tasks",
    )
    d = job.to_dict()
    assert d["id"] == "daily-summary"
    assert d["schedule"] == "0 9 * * *"
    assert d["agentId"] == "main"


def test_scheduler_add_remove():
    sched = CronScheduler()
    job = CronJob(id="j1", name="Test", schedule="0 * * * *")
    sched.add_job(job)

    assert len(sched.list_jobs()) == 1
    assert sched.get_job("j1") is job

    removed = sched.remove_job("j1")
    assert removed is True
    assert len(sched.list_jobs()) == 0


def test_scheduler_remove_nonexistent():
    sched = CronScheduler()
    assert sched.remove_job("nope") is False


def test_scheduler_list_jobs():
    sched = CronScheduler()
    sched.add_job(CronJob(id="a", name="A", schedule="0 * * * *"))
    sched.add_job(CronJob(id="b", name="B", schedule="30 * * * *", enabled=False))

    jobs = sched.list_jobs()
    assert len(jobs) == 2
    ids = {j.id for j in jobs}
    assert ids == {"a", "b"}
