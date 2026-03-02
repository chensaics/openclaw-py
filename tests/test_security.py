"""Tests for security — DM/group policy and audit."""

from __future__ import annotations

import pytest

from pyclaw.security.dm_policy import (
    DmGroupAccessDecision,
    resolve_dm_group_access,
    resolve_effective_allow_from,
)
from pyclaw.security.audit import AuditSeverity, run_security_audit


class TestResolveEffectiveAllowFrom:
    def test_empty(self):
        result = resolve_effective_allow_from()
        assert result == set()

    def test_config_only(self):
        result = resolve_effective_allow_from(config_allow_list=["alice", "bob"])
        assert result == {"alice", "bob"}

    def test_pairing_only(self):
        result = resolve_effective_allow_from(pairing_allow_list=["charlie"])
        assert result == {"charlie"}

    def test_merge(self):
        result = resolve_effective_allow_from(
            config_allow_list=["alice"],
            pairing_allow_list=["bob"],
        )
        assert result == {"alice", "bob"}

    def test_dedup(self):
        result = resolve_effective_allow_from(
            config_allow_list=["alice"],
            pairing_allow_list=["alice"],
        )
        assert result == {"alice"}


class TestResolveDmGroupAccess:
    def test_open_policy_allows_anyone(self):
        decision = resolve_dm_group_access("stranger", dm_policy="open")
        assert decision == DmGroupAccessDecision.ALLOW

    def test_disabled_policy_blocks(self):
        decision = resolve_dm_group_access("anyone", dm_policy="disabled")
        assert decision == DmGroupAccessDecision.BLOCK

    def test_allowlist_allowed(self):
        decision = resolve_dm_group_access(
            "alice", dm_policy="allowlist", config_allow_list=["alice"],
        )
        assert decision == DmGroupAccessDecision.ALLOW

    def test_allowlist_blocked(self):
        decision = resolve_dm_group_access(
            "stranger", dm_policy="allowlist", config_allow_list=["alice"],
        )
        assert decision == DmGroupAccessDecision.BLOCK

    def test_pairing_policy(self):
        decision = resolve_dm_group_access("stranger", dm_policy="pairing")
        assert decision == DmGroupAccessDecision.PAIRING

    def test_group_allowlist_allowed(self):
        decision = resolve_dm_group_access(
            "alice", is_group=True, group_policy="allowlist",
            config_allow_list=["alice"],
        )
        assert decision == DmGroupAccessDecision.ALLOW

    def test_group_disabled(self):
        decision = resolve_dm_group_access(
            "alice", is_group=True, group_policy="disabled",
        )
        assert decision == DmGroupAccessDecision.BLOCK


class TestSecurityAudit:
    def test_basic_audit_no_crash(self):
        result = run_security_audit()
        assert hasattr(result, "findings")
        assert isinstance(result.critical_count, int)
        assert isinstance(result.warning_count, int)

    def test_audit_with_config(self):
        config = {"gateway": {"auth": {"token": ""}}}
        result = run_security_audit(config)
        assert isinstance(result.findings, list)

    def test_audit_deep(self):
        result = run_security_audit(deep=True)
        assert isinstance(result.findings, list)
