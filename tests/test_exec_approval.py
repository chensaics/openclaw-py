"""Tests for exec approval and system.run binding."""

from __future__ import annotations

import pytest

from pyclaw.security.exec_approval import (
    ApprovalDecision,
    CommandArgvRule,
    ExecApprovalPolicy,
    ExecRequest,
    SystemRunApprovalBindingV1,
)


class TestCommandArgvRule:
    def test_exact_match(self) -> None:
        rule = CommandArgvRule(pattern=["git", "status"])
        assert rule.matches(["git", "status"]) is True
        assert rule.matches(["git", "push"]) is False
        assert rule.matches(["git"]) is False

    def test_glob_match(self) -> None:
        rule = CommandArgvRule(pattern=["git", "*"])
        assert rule.matches(["git", "status"]) is True
        assert rule.matches(["git", "push"]) is True
        assert rule.matches(["npm", "install"]) is False

    def test_prefix_match(self) -> None:
        rule = CommandArgvRule(pattern=["npm", "..."])
        assert rule.matches(["npm", "install", "--save"]) is True
        assert rule.matches(["npm"]) is True
        assert rule.matches(["git"]) is False

    def test_fnmatch_pattern(self) -> None:
        rule = CommandArgvRule(pattern=["python*.py"])
        assert rule.matches(["python3.py"]) is True
        # Does not match multi-segment
        assert rule.matches(["python3.py", "arg"]) is False

    def test_empty_pattern(self) -> None:
        rule = CommandArgvRule(pattern=[])
        assert rule.matches(["anything"]) is False

    def test_argv_shorter_than_pattern(self) -> None:
        rule = CommandArgvRule(pattern=["git", "push", "origin"])
        assert rule.matches(["git", "push"]) is False


class TestSystemRunApprovalBindingV1:
    def test_evaluate_allow(self) -> None:
        binding = SystemRunApprovalBindingV1(
            rules=[
                CommandArgvRule(pattern=["git", "..."], decision=ApprovalDecision.ALLOW),
            ]
        )
        assert binding.evaluate(["git", "status"]) == ApprovalDecision.ALLOW

    def test_evaluate_deny(self) -> None:
        binding = SystemRunApprovalBindingV1(
            rules=[
                CommandArgvRule(pattern=["rm", "-rf", "..."], decision=ApprovalDecision.DENY),
            ]
        )
        assert binding.evaluate(["rm", "-rf", "/"]) == ApprovalDecision.DENY

    def test_evaluate_default_prompt(self) -> None:
        binding = SystemRunApprovalBindingV1(
            rules=[
                CommandArgvRule(pattern=["git", "..."], decision=ApprovalDecision.ALLOW),
            ]
        )
        assert binding.evaluate(["npm", "install"]) == ApprovalDecision.PROMPT

    def test_evaluate_cwd_denied(self) -> None:
        binding = SystemRunApprovalBindingV1(
            denied_cwd_patterns=["/etc/*"],
            rules=[
                CommandArgvRule(pattern=["cat", "..."], decision=ApprovalDecision.ALLOW),
            ],
        )
        assert binding.evaluate(["cat", "passwd"], cwd="/etc/ssh") == ApprovalDecision.DENY

    def test_evaluate_cwd_allowed(self) -> None:
        binding = SystemRunApprovalBindingV1(
            allowed_cwd_patterns=["/home/*"],
            rules=[
                CommandArgvRule(pattern=["ls", "..."], decision=ApprovalDecision.ALLOW),
            ],
        )
        assert binding.evaluate(["ls"], cwd="/home/user") == ApprovalDecision.ALLOW
        assert binding.evaluate(["ls"], cwd="/root") == ApprovalDecision.DENY

    def test_env_key_allowed(self) -> None:
        binding = SystemRunApprovalBindingV1(
            allowed_env_keys=["PATH", "HOME"],
        )
        assert binding.is_env_key_allowed("PATH") is True
        assert binding.is_env_key_allowed("SECRET") is False

    def test_env_passthrough(self) -> None:
        binding = SystemRunApprovalBindingV1(allow_env_passthrough=True)
        assert binding.is_env_key_allowed("ANYTHING") is True

    def test_from_dict(self) -> None:
        data = {
            "version": 1,
            "defaultDecision": "deny",
            "rules": [
                {"pattern": ["git", "*"], "decision": "allow", "description": "git ops"},
            ],
            "allowedCwdPatterns": ["/workspace/*"],
            "maxTimeoutMs": 60000,
        }
        binding = SystemRunApprovalBindingV1.from_dict(data)
        assert binding.default_decision == ApprovalDecision.DENY
        assert len(binding.rules) == 1
        assert binding.max_timeout_ms == 60000

    def test_to_dict_roundtrip(self) -> None:
        binding = SystemRunApprovalBindingV1(
            rules=[
                CommandArgvRule(pattern=["ls"], decision=ApprovalDecision.ALLOW),
            ],
            allowed_cwd_patterns=["/home/*"],
        )
        d = binding.to_dict()
        restored = SystemRunApprovalBindingV1.from_dict(d)
        assert restored.rules[0].pattern == ["ls"]
        assert restored.allowed_cwd_patterns == ["/home/*"]


class TestExecRequest:
    def test_auto_parse_argv(self) -> None:
        req = ExecRequest(command="git status")
        assert req.argv == ["git", "status"]

    def test_explicit_argv(self) -> None:
        req = ExecRequest(command="git status", argv=["git", "status", "--short"])
        assert req.argv == ["git", "status", "--short"]


class TestExecApprovalPolicy:
    def test_global_deny(self) -> None:
        policy = ExecApprovalPolicy()
        req = ExecRequest(command="rm -rf /")
        result = policy.evaluate(req)
        assert result.decision == ApprovalDecision.DENY

    def test_binding_allow(self) -> None:
        binding = SystemRunApprovalBindingV1(
            rules=[
                CommandArgvRule(pattern=["echo", "..."], decision=ApprovalDecision.ALLOW),
            ]
        )
        policy = ExecApprovalPolicy([binding])
        req = ExecRequest(command="echo hello")
        result = policy.evaluate(req)
        assert result.decision == ApprovalDecision.ALLOW

    def test_timeout_exceed(self) -> None:
        binding = SystemRunApprovalBindingV1(max_timeout_ms=5000)
        policy = ExecApprovalPolicy([binding])
        req = ExecRequest(command="sleep 100", timeout_ms=10000)
        result = policy.evaluate(req)
        assert result.decision == ApprovalDecision.DENY

    def test_default_prompt(self) -> None:
        policy = ExecApprovalPolicy()
        req = ExecRequest(command="some-unknown-cmd")
        result = policy.evaluate(req)
        assert result.decision == ApprovalDecision.PROMPT

    def test_env_sanitization(self) -> None:
        binding = SystemRunApprovalBindingV1(
            rules=[
                CommandArgvRule(pattern=["env", "..."], decision=ApprovalDecision.ALLOW),
            ],
            allowed_env_keys=["PATH"],
        )
        policy = ExecApprovalPolicy([binding])
        req = ExecRequest(command="env", env={"PATH": "/usr/bin", "SECRET": "s3cret"})
        result = policy.evaluate(req)
        assert result.decision == ApprovalDecision.ALLOW
        assert "PATH" in result.sanitized_env
        assert "SECRET" not in result.sanitized_env
