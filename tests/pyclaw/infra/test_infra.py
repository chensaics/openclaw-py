"""Tests for infra — exec approvals, heartbeat, update check."""

from __future__ import annotations

import tempfile
from pathlib import Path

from pyclaw.infra.exec_approvals import (
    AgentExecConfig,
    ExecAllowlistEntry,
    ExecApprovalsFile,
    add_allowlist_entry,
    check_allowlist,
    load_exec_approvals,
    requires_exec_approval,
    resolve_exec_config,
    save_exec_approvals,
)
from pyclaw.infra.heartbeat import HeartbeatConfig, is_within_active_hours, parse_duration_ms
from pyclaw.infra.update_check import (
    compare_semver,
    detect_install_kind,
    resolve_effective_update_channel,
)


class TestExecApprovals:
    def test_load_save_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            sd = Path(td)
            approvals = ExecApprovalsFile(version=1)
            approvals.agents["main"] = AgentExecConfig(
                security="allowlist",
                allowlist=[ExecAllowlistEntry(pattern="ls")],
            )
            save_exec_approvals(approvals, sd)
            loaded = load_exec_approvals(sd)
            assert loaded.version == 1
            assert "main" in loaded.agents
            assert loaded.agents["main"].allowlist[0].pattern == "ls"

    def test_load_missing_file(self):
        with tempfile.TemporaryDirectory() as td:
            loaded = load_exec_approvals(Path(td))
            assert loaded.version == 1
            assert loaded.agents == {}

    def test_check_allowlist_match(self):
        entries = [ExecAllowlistEntry(pattern="ls"), ExecAllowlistEntry(pattern="cat")]
        assert check_allowlist("ls -la", entries) is not None
        assert check_allowlist("rm -rf", entries) is None

    def test_requires_approval_deny(self):
        config = AgentExecConfig(security="deny")
        assert requires_exec_approval("anything", config) is True

    def test_requires_approval_full(self):
        config = AgentExecConfig(security="full", ask="off")
        assert requires_exec_approval("anything", config) is False

    def test_requires_approval_full_always(self):
        config = AgentExecConfig(security="full", ask="always")
        assert requires_exec_approval("anything", config) is True

    def test_requires_approval_allowlist_hit(self):
        config = AgentExecConfig(
            security="allowlist",
            ask="on-miss",
            allowlist=[ExecAllowlistEntry(pattern="ls")],
        )
        assert requires_exec_approval("ls", config) is False

    def test_requires_approval_allowlist_miss(self):
        config = AgentExecConfig(
            security="allowlist",
            ask="on-miss",
            allowlist=[ExecAllowlistEntry(pattern="ls")],
        )
        assert requires_exec_approval("rm", config) is True

    def test_resolve_exec_config_agent(self):
        approvals = ExecApprovalsFile()
        approvals.agents["test"] = AgentExecConfig(security="full")
        cfg = resolve_exec_config("test", approvals)
        assert cfg.security == "full"

    def test_resolve_exec_config_defaults(self):
        approvals = ExecApprovalsFile()
        approvals.defaults = AgentExecConfig(security="deny")
        cfg = resolve_exec_config("unknown", approvals)
        assert cfg.security == "deny"

    def test_add_allowlist_entry(self):
        with tempfile.TemporaryDirectory() as td:
            sd = Path(td)
            add_allowlist_entry("main", "git.*", "git status", sd)
            loaded = load_exec_approvals(sd)
            assert len(loaded.agents["main"].allowlist) == 1


class TestHeartbeat:
    def test_parse_duration_ms(self):
        assert parse_duration_ms("5s") == 5000
        assert parse_duration_ms("2m") == 120000
        assert parse_duration_ms("1h") == 3600000
        assert parse_duration_ms("500ms") == 500
        # Plain number without unit falls back to default (30m)
        assert parse_duration_ms("1000") == 30 * 60 * 1000

    def test_is_within_active_hours_all_day(self):
        config = HeartbeatConfig()
        assert is_within_active_hours(config) is True

    def test_is_within_active_hours_range(self):
        import time

        now_hour = int(time.strftime("%H"))
        config = HeartbeatConfig(active_hours=f"{now_hour}:00-{now_hour + 1}:00")
        assert is_within_active_hours(config) is True


class TestUpdateCheck:
    def test_compare_semver(self):
        assert compare_semver("1.0.0", "1.0.0") == 0
        assert compare_semver("1.0.1", "1.0.0") > 0
        assert compare_semver("1.0.0", "2.0.0") < 0
        assert compare_semver("2026.2.28", "2026.2.27") > 0

    def test_detect_install_kind(self):
        kind = detect_install_kind()
        assert kind in ("git", "package", "unknown")

    def test_resolve_effective_update_channel(self):
        ch = resolve_effective_update_channel(config_channel="beta")
        assert ch == "beta"

        ch2 = resolve_effective_update_channel()
        assert ch2 in ("stable", "beta", "dev")
