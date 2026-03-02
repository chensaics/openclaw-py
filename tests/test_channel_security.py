"""Tests for Phase 20 — channel security: auth guard, allowlist boundaries,
audit extensions, and dangerous tools."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pyclaw.channels.auth_guard import (
    AuthAction,
    AuthDecision,
    AuthRequest,
    AuthRateLimiter,
    ChannelAuthConfig,
    ChannelAuthGuard,
)
from pyclaw.security.allowlist_boundaries import (
    AllowlistBoundaryStore,
    AllowlistEntry,
    AllowlistScope,
    AllowlistSource,
    validate_pairing_dm_only,
)
from pyclaw.security.audit_extra import (
    audit_channels,
    audit_gateway_http,
    audit_hooks,
    audit_plugins,
    run_extended_audit,
)
from pyclaw.security.dangerous_tools import (
    DangerousToolDef,
    ExternalContentAction,
    ExternalContentPolicy,
    RiskCategory,
    SkillScanFinding,
    filter_tools_by_risk,
    get_all_dangerous_tools,
    get_tool_risk,
    is_tool_dangerous,
    register_dangerous_tool,
    requires_approval,
    sanitize_html_content,
    scan_skill_file,
)


# ===== Auth Guard =====

class TestAuthRateLimiter:
    def test_allows_under_limit(self) -> None:
        limiter = AuthRateLimiter(max_per_minute=5)
        for _ in range(5):
            assert limiter.check("user1") is True

    def test_blocks_over_limit(self) -> None:
        limiter = AuthRateLimiter(max_per_minute=3)
        for _ in range(3):
            limiter.check("user1")
        assert limiter.check("user1") is False

    def test_separate_users(self) -> None:
        limiter = AuthRateLimiter(max_per_minute=2)
        limiter.check("user1")
        limiter.check("user1")
        assert limiter.check("user1") is False
        assert limiter.check("user2") is True

    def test_reset(self) -> None:
        limiter = AuthRateLimiter(max_per_minute=1)
        limiter.check("user1")
        assert limiter.check("user1") is False
        limiter.reset("user1")
        assert limiter.check("user1") is True


class TestChannelAuthGuard:
    @pytest.fixture
    def guard(self) -> ChannelAuthGuard:
        g = ChannelAuthGuard()
        g.register_channel(ChannelAuthConfig(
            channel_id="telegram",
            dm_policy="allowlist",
            config_allow_list=["user1", "user2"],
            owner_ids={"owner1"},
        ))
        return g

    def test_allow_listed_user(self, guard: ChannelAuthGuard) -> None:
        req = AuthRequest(channel_id="telegram", sender_id="user1", action=AuthAction.MESSAGE)
        resp = guard.check(req)
        assert resp.decision == AuthDecision.ALLOW

    def test_deny_unlisted_user(self, guard: ChannelAuthGuard) -> None:
        req = AuthRequest(channel_id="telegram", sender_id="stranger", action=AuthAction.MESSAGE)
        resp = guard.check(req)
        assert resp.decision == AuthDecision.DENY

    def test_owner_bypass(self, guard: ChannelAuthGuard) -> None:
        req = AuthRequest(channel_id="telegram", sender_id="owner1", action=AuthAction.MESSAGE)
        resp = guard.check(req)
        assert resp.decision == AuthDecision.ALLOW

    def test_unknown_channel_denied(self, guard: ChannelAuthGuard) -> None:
        req = AuthRequest(channel_id="unknown", sender_id="user1", action=AuthAction.MESSAGE)
        resp = guard.check(req)
        assert resp.decision == AuthDecision.DENY

    def test_pairing_policy(self) -> None:
        guard = ChannelAuthGuard()
        guard.register_channel(ChannelAuthConfig(
            channel_id="telegram",
            dm_policy="pairing",
        ))
        req = AuthRequest(channel_id="telegram", sender_id="new_user", action=AuthAction.MESSAGE)
        resp = guard.check(req)
        assert resp.decision == AuthDecision.PAIRING

    def test_reaction_denied_when_disabled(self) -> None:
        guard = ChannelAuthGuard()
        guard.register_channel(ChannelAuthConfig(
            channel_id="feishu",
            allow_reactions=False,
        ))
        req = AuthRequest(channel_id="feishu", sender_id="user1", action=AuthAction.REACTION)
        resp = guard.check(req)
        assert resp.decision == AuthDecision.DENY

    def test_reaction_allowed(self) -> None:
        guard = ChannelAuthGuard()
        guard.register_channel(ChannelAuthConfig(
            channel_id="feishu",
            allow_reactions=True,
        ))
        req = AuthRequest(channel_id="feishu", sender_id="user1", action=AuthAction.REACTION)
        resp = guard.check(req)
        assert resp.decision == AuthDecision.ALLOW

    def test_file_upload_denied(self) -> None:
        guard = ChannelAuthGuard()
        guard.register_channel(ChannelAuthConfig(
            channel_id="telegram",
            allow_file_uploads=False,
        ))
        req = AuthRequest(channel_id="telegram", sender_id="user1", action=AuthAction.FILE_UPLOAD)
        resp = guard.check(req)
        assert resp.decision == AuthDecision.DENY

    def test_deny_log(self, guard: ChannelAuthGuard) -> None:
        req = AuthRequest(channel_id="telegram", sender_id="stranger", action=AuthAction.MESSAGE)
        guard.check(req)
        deny_log = guard.get_deny_log()
        assert len(deny_log) >= 1
        assert deny_log[-1].decision == AuthDecision.DENY

    def test_group_message_denied(self) -> None:
        guard = ChannelAuthGuard()
        guard.register_channel(ChannelAuthConfig(
            channel_id="discord",
            group_policy="allowlist",
            config_allow_list=["user1"],
        ))
        req = AuthRequest(
            channel_id="discord", sender_id="stranger",
            action=AuthAction.MESSAGE, is_group=True,
        )
        resp = guard.check(req)
        assert resp.decision == AuthDecision.DENY

    def test_unregister_channel(self, guard: ChannelAuthGuard) -> None:
        guard.unregister_channel("telegram")
        req = AuthRequest(channel_id="telegram", sender_id="user1", action=AuthAction.MESSAGE)
        resp = guard.check(req)
        assert resp.decision == AuthDecision.DENY


# ===== Allowlist Boundaries =====

class TestAllowlistBoundaryStore:
    def test_dm_entry_allows_dm(self) -> None:
        store = AllowlistBoundaryStore()
        store.add_entry(AllowlistEntry(sender_id="u1", scope=AllowlistScope.DM))
        assert store.is_allowed("u1", is_group=False) is True

    def test_dm_entry_blocks_group(self) -> None:
        store = AllowlistBoundaryStore()
        store.add_entry(AllowlistEntry(sender_id="u1", scope=AllowlistScope.DM))
        assert store.is_allowed("u1", is_group=True) is False

    def test_group_entry_allows_group(self) -> None:
        store = AllowlistBoundaryStore()
        store.add_entry(AllowlistEntry(sender_id="u1", scope=AllowlistScope.GROUP))
        assert store.is_allowed("u1", is_group=True) is True

    def test_group_entry_blocks_dm(self) -> None:
        store = AllowlistBoundaryStore()
        store.add_entry(AllowlistEntry(sender_id="u1", scope=AllowlistScope.GROUP))
        assert store.is_allowed("u1", is_group=False) is False

    def test_both_scope(self) -> None:
        store = AllowlistBoundaryStore()
        store.add_entry(AllowlistEntry(sender_id="u1", scope=AllowlistScope.BOTH))
        assert store.is_allowed("u1", is_group=False) is True
        assert store.is_allowed("u1", is_group=True) is True

    def test_pairing_forced_to_dm(self) -> None:
        store = AllowlistBoundaryStore()
        store.add_entry(AllowlistEntry(
            sender_id="u1", scope=AllowlistScope.BOTH,
            source=AllowlistSource.PAIRING,
        ))
        # Should be forced to DM scope
        assert store.is_allowed("u1", is_group=False) is True
        assert store.is_allowed("u1", is_group=True) is False

    def test_violations_logged(self) -> None:
        store = AllowlistBoundaryStore()
        store.add_entry(AllowlistEntry(
            sender_id="u1", scope=AllowlistScope.GROUP,
            source=AllowlistSource.PAIRING,
        ))
        violations = store.get_violations()
        assert len(violations) == 1
        assert "pairing" in violations[0].violation_type

    def test_channel_specific(self) -> None:
        store = AllowlistBoundaryStore()
        store.add_entry(AllowlistEntry(sender_id="u1", scope=AllowlistScope.DM, channel_id="telegram"))
        assert store.is_allowed("u1", channel_id="telegram") is True
        # Falls back to global (none)
        assert store.is_allowed("u1", channel_id="discord") is False

    def test_get_dm_allowed(self) -> None:
        store = AllowlistBoundaryStore()
        store.add_entry(AllowlistEntry(sender_id="u1", scope=AllowlistScope.DM))
        store.add_entry(AllowlistEntry(sender_id="u2", scope=AllowlistScope.GROUP))
        store.add_entry(AllowlistEntry(sender_id="u3", scope=AllowlistScope.BOTH))
        dm_allowed = store.get_dm_allowed()
        assert "u1" in dm_allowed
        assert "u2" not in dm_allowed
        assert "u3" in dm_allowed

    def test_get_group_allowed(self) -> None:
        store = AllowlistBoundaryStore()
        store.add_entry(AllowlistEntry(sender_id="u1", scope=AllowlistScope.DM))
        store.add_entry(AllowlistEntry(sender_id="u2", scope=AllowlistScope.GROUP))
        group_allowed = store.get_group_allowed()
        assert "u1" not in group_allowed
        assert "u2" in group_allowed

    def test_remove_entry(self) -> None:
        store = AllowlistBoundaryStore()
        store.add_entry(AllowlistEntry(sender_id="u1", scope=AllowlistScope.DM))
        store.remove_entry("u1")
        assert store.is_allowed("u1") is False


class TestValidatePairingDmOnly:
    def test_valid_dm_entries(self) -> None:
        entries, violations = validate_pairing_dm_only([
            {"sender_id": "u1", "scope": "dm"},
            {"sender_id": "u2"},  # default is dm
        ])
        assert len(entries) == 2
        assert len(violations) == 0

    def test_non_dm_forced(self) -> None:
        entries, violations = validate_pairing_dm_only([
            {"sender_id": "u1", "scope": "group"},
        ])
        assert len(entries) == 1
        assert entries[0].scope == AllowlistScope.DM
        assert len(violations) == 1


# ===== Audit Extensions =====

class TestAuditGatewayHttp:
    def test_nonlocal_no_tls(self) -> None:
        findings = audit_gateway_http({"gateway": {"bind": "0.0.0.0"}})
        assert any(f.id == "gateway-no-tls-nonlocal" for f in findings)

    def test_loopback_ok(self) -> None:
        findings = audit_gateway_http({"gateway": {"bind": "loopback"}})
        assert not any(f.id == "gateway-no-tls-nonlocal" for f in findings)

    def test_cors_wildcard(self) -> None:
        findings = audit_gateway_http({"gateway": {"cors": {"origins": ["*"]}}})
        assert any(f.id == "gateway-cors-wildcard" for f in findings)

    def test_weak_tls(self) -> None:
        findings = audit_gateway_http({
            "gateway": {"tls": {"enabled": True, "minVersion": "TLSv1"}},
        })
        assert any(f.id == "gateway-weak-tls" for f in findings)


class TestAuditPlugins:
    def test_exec_permission(self) -> None:
        findings = audit_plugins({
            "plugins": {"installed": [{"name": "evil", "permissions": ["exec"]}]},
        })
        assert any("exec-permission" in f.id for f in findings)

    def test_untrusted_source(self) -> None:
        findings = audit_plugins({
            "plugins": {"installed": [{"name": "unknown", "source": "github:evil/pkg"}]},
        })
        assert any("untrusted-source" in f.id for f in findings)

    def test_trusted_source(self) -> None:
        findings = audit_plugins({
            "plugins": {"installed": [{"name": "memory", "source": "@pyclaw/memory-core"}]},
        })
        assert not any("untrusted-source" in f.id for f in findings)


class TestAuditHooks:
    def test_shell_exec(self) -> None:
        findings = audit_hooks({
            "hooks": {"on_message": {"handler": "bash -c 'rm -rf /'"}},
        })
        assert any("shell-exec" in f.id for f in findings)

    def test_insecure_url(self) -> None:
        findings = audit_hooks({
            "hooks": {"webhook": {"url": "http://example.com/hook"}},
        })
        assert any("insecure-url" in f.id for f in findings)


class TestAuditChannels:
    def test_open_dm(self) -> None:
        findings = audit_channels({
            "channels": {"telegram": {"dmPolicy": "open"}},
        })
        assert any("open-dm" in f.id for f in findings)

    def test_empty_allowlist(self) -> None:
        findings = audit_channels({
            "channels": {"telegram": {"dmPolicy": "allowlist"}},
        })
        assert any("empty-allowlist" in f.id for f in findings)

    def test_plaintext_token(self) -> None:
        findings = audit_channels({
            "channels": {"telegram": {"token": "123456:ABC-DEF"}},
        })
        assert any("plaintext-secret" in f.id for f in findings)

    def test_env_ref_ok(self) -> None:
        findings = audit_channels({
            "channels": {"telegram": {"token": "$TELEGRAM_TOKEN"}},
        })
        assert not any("plaintext-secret" in f.id for f in findings)


class TestRunExtendedAudit:
    def test_clean_config(self) -> None:
        result = run_extended_audit({
            "gateway": {"bind": "loopback"},
        })
        assert any(f.id == "extended-all-clear" for f in result.findings)

    def test_multiple_findings(self) -> None:
        result = run_extended_audit({
            "gateway": {"bind": "0.0.0.0"},
            "channels": {"telegram": {"dmPolicy": "open"}},
        })
        assert len(result.findings) >= 2


# ===== Dangerous Tools =====

class TestDangerousTools:
    def test_system_run_is_dangerous(self) -> None:
        assert is_tool_dangerous("system_run") is True

    def test_safe_tool_not_dangerous(self) -> None:
        assert is_tool_dangerous("file_read") is False

    def test_get_tool_risk(self) -> None:
        risk = get_tool_risk("system_run")
        assert risk is not None
        assert RiskCategory.EXEC in risk.risk_categories

    def test_requires_approval(self) -> None:
        assert requires_approval("system_run") is True
        assert requires_approval("web_search") is False

    def test_get_all_dangerous(self) -> None:
        all_tools = get_all_dangerous_tools()
        assert "system_run" in all_tools
        assert "file_write" in all_tools

    def test_register_custom(self) -> None:
        register_dangerous_tool(DangerousToolDef(
            tool_name="custom_danger",
            risk_categories=[RiskCategory.DESTRUCTIVE],
            max_risk_level=3,
        ))
        assert is_tool_dangerous("custom_danger") is True

    def test_filter_by_risk_level(self) -> None:
        tools = ["system_run", "web_fetch", "file_read", "unknown_tool"]
        filtered = filter_tools_by_risk(tools, max_risk_level=1)
        assert "system_run" not in filtered
        assert "web_fetch" in filtered
        assert "file_read" in filtered
        assert "unknown_tool" in filtered

    def test_filter_by_category(self) -> None:
        tools = ["system_run", "web_fetch", "file_read"]
        filtered = filter_tools_by_risk(tools, exclude_categories=[RiskCategory.EXEC])
        assert "system_run" not in filtered
        assert "web_fetch" in filtered


class TestSkillScanner:
    def test_scan_clean_file(self, tmp_path: Path) -> None:
        clean = tmp_path / "clean.md"
        clean.write_text("# Safe Skill\n\nThis skill does nothing dangerous.")
        findings = scan_skill_file(clean)
        assert len(findings) == 0

    def test_scan_dangerous_file(self, tmp_path: Path) -> None:
        dangerous = tmp_path / "danger.py"
        dangerous.write_text("import os\nos.system('rm -rf /')\neval(user_input)")
        findings = scan_skill_file(dangerous)
        assert len(findings) >= 2
        assert any(f.severity == "critical" for f in findings)

    def test_scan_nonexistent(self) -> None:
        findings = scan_skill_file("/nonexistent/file.md")
        assert len(findings) == 0

    def test_hardcoded_secret(self, tmp_path: Path) -> None:
        secret_file = tmp_path / "config.py"
        secret_file.write_text("api_key = 'sk-abcdefghijklmnopqrstuvwxyz'")
        findings = scan_skill_file(secret_file)
        assert any("secret" in f.detail.lower() for f in findings)


class TestExternalContentPolicy:
    def test_default_allows_https(self) -> None:
        policy = ExternalContentPolicy()
        assert policy.check_url("https://example.com") != ExternalContentAction.BLOCK

    def test_blocks_file_scheme(self) -> None:
        policy = ExternalContentPolicy()
        assert policy.check_url("file:///etc/passwd") == ExternalContentAction.BLOCK

    def test_blocks_ftp(self) -> None:
        policy = ExternalContentPolicy()
        assert policy.check_url("ftp://evil.com/file") == ExternalContentAction.BLOCK

    def test_blocks_data_url(self) -> None:
        policy = ExternalContentPolicy()
        assert policy.check_url("data:text/html,<h1>hi</h1>") == ExternalContentAction.BLOCK

    def test_allows_data_url_when_enabled(self) -> None:
        policy = ExternalContentPolicy(allow_data_urls=True)
        assert policy.check_url("data:text/plain,hello") != ExternalContentAction.BLOCK

    def test_blocked_domain(self) -> None:
        policy = ExternalContentPolicy(blocked_domains=["evil.com"])
        assert policy.check_url("https://evil.com/payload") == ExternalContentAction.BLOCK

    def test_fetch_disabled(self) -> None:
        policy = ExternalContentPolicy(allow_url_fetch=False)
        assert policy.check_url("https://safe.com") == ExternalContentAction.BLOCK

    def test_file_read_disabled(self) -> None:
        policy = ExternalContentPolicy(allow_file_read=False)
        assert policy.check_file_path("/etc/passwd") == ExternalContentAction.BLOCK


class TestSanitizeHtml:
    def test_strip_scripts(self) -> None:
        html = '<div>Hello</div><script>alert("xss")</script>'
        result = sanitize_html_content(html)
        assert "<script" not in result
        assert "Hello" in result

    def test_strip_iframes(self) -> None:
        html = '<p>Safe</p><iframe src="evil.com"></iframe>'
        result = sanitize_html_content(html)
        assert "<iframe" not in result
        assert "Safe" in result

    def test_strip_event_handlers(self) -> None:
        html = '<img src="x" onerror="alert(1)">'
        result = sanitize_html_content(html)
        assert "onerror" not in result

    def test_strip_javascript_urls(self) -> None:
        html = '<a href="javascript:alert(1)">click</a>'
        result = sanitize_html_content(html)
        assert "javascript:" not in result

    def test_preserves_safe_content(self) -> None:
        html = '<p>Hello <b>world</b></p>'
        result = sanitize_html_content(html)
        assert result == html
