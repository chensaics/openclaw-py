"""Exec approval — command execution gating with binding policies.

Ported from ``src/security/exec-approval.ts`` and
``src/security/system-run-binding.ts``.

Provides ``SystemRunApprovalBindingV1`` for fine-grained control of
which commands agents can execute, plus ``ExecApprovalPolicy`` for
runtime gating decisions.
"""

from __future__ import annotations

import fnmatch
import logging
import re
import shlex
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ApprovalDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    PROMPT = "prompt"


@dataclass
class CommandArgvRule:
    """A rule matching a specific command argv pattern.

    ``pattern`` supports:
    - Exact match: ``["git", "status"]``
    - Glob: ``["git", "*"]``
    - Prefix match: ``["npm", "..."]`` (``...`` matches rest)
    """

    pattern: list[str]
    decision: ApprovalDecision = ApprovalDecision.ALLOW
    description: str = ""

    def matches(self, argv: list[str]) -> bool:
        """Check if this rule matches the given argv."""
        if not self.pattern:
            return False

        for i, pat in enumerate(self.pattern):
            if pat == "...":
                return True
            if i >= len(argv):
                return False
            if pat != "*" and not fnmatch.fnmatch(argv[i], pat):
                return False

        # If pattern has no "..." at end, lengths must match
        if len(self.pattern) > 0 and self.pattern[-1] != "...":
            return len(argv) == len(self.pattern)
        return True


@dataclass
class SystemRunApprovalBindingV1:
    """V1 binding for system.run command approval.

    Defines a set of rules for which commands are pre-approved,
    denied, or require user prompt.
    """

    version: int = 1
    default_decision: ApprovalDecision = ApprovalDecision.PROMPT
    rules: list[CommandArgvRule] = field(default_factory=list)
    allowed_cwd_patterns: list[str] = field(default_factory=list)
    denied_cwd_patterns: list[str] = field(default_factory=list)
    max_timeout_ms: int = 300_000
    allow_env_passthrough: bool = False
    allowed_env_keys: list[str] = field(default_factory=list)

    def evaluate(self, argv: list[str], *, cwd: str = "") -> ApprovalDecision:
        """Evaluate a command against the binding rules."""
        if cwd:
            if self.denied_cwd_patterns:
                for pat in self.denied_cwd_patterns:
                    if fnmatch.fnmatch(cwd, pat):
                        return ApprovalDecision.DENY

            if self.allowed_cwd_patterns:
                matched = any(fnmatch.fnmatch(cwd, p) for p in self.allowed_cwd_patterns)
                if not matched:
                    return ApprovalDecision.DENY

        for rule in self.rules:
            if rule.matches(argv):
                return rule.decision

        return self.default_decision

    def is_env_key_allowed(self, key: str) -> bool:
        """Check if an environment variable key is allowed to pass through."""
        if self.allow_env_passthrough:
            return True
        return key in self.allowed_env_keys

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SystemRunApprovalBindingV1:
        rules = []
        for rd in data.get("rules", []):
            rules.append(CommandArgvRule(
                pattern=rd.get("pattern", []),
                decision=ApprovalDecision(rd.get("decision", "allow")),
                description=rd.get("description", ""),
            ))

        return cls(
            version=data.get("version", 1),
            default_decision=ApprovalDecision(data.get("defaultDecision", "prompt")),
            rules=rules,
            allowed_cwd_patterns=data.get("allowedCwdPatterns", []),
            denied_cwd_patterns=data.get("deniedCwdPatterns", []),
            max_timeout_ms=data.get("maxTimeoutMs", 300_000),
            allow_env_passthrough=data.get("allowEnvPassthrough", False),
            allowed_env_keys=data.get("allowedEnvKeys", []),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "defaultDecision": self.default_decision.value,
            "rules": [
                {
                    "pattern": r.pattern,
                    "decision": r.decision.value,
                    "description": r.description,
                }
                for r in self.rules
            ],
            "allowedCwdPatterns": self.allowed_cwd_patterns,
            "deniedCwdPatterns": self.denied_cwd_patterns,
            "maxTimeoutMs": self.max_timeout_ms,
            "allowEnvPassthrough": self.allow_env_passthrough,
            "allowedEnvKeys": self.allowed_env_keys,
        }


# ---------------------------------------------------------------------------
# ExecApprovalPolicy — runtime gating
# ---------------------------------------------------------------------------

@dataclass
class ExecRequest:
    """A request to execute a command."""

    command: str
    argv: list[str] = field(default_factory=list)
    cwd: str = ""
    env: dict[str, str] = field(default_factory=dict)
    timeout_ms: int = 30_000
    agent_id: str = ""
    session_key: str = ""

    def __post_init__(self) -> None:
        if not self.argv and self.command:
            try:
                self.argv = shlex.split(self.command)
            except ValueError:
                self.argv = self.command.split()


@dataclass
class ExecApprovalResult:
    """Result of an exec approval check."""

    decision: ApprovalDecision
    reason: str = ""
    matched_rule: str = ""
    sanitized_env: dict[str, str] = field(default_factory=dict)


class ExecApprovalPolicy:
    """Runtime exec approval policy using bindings."""

    def __init__(
        self,
        bindings: list[SystemRunApprovalBindingV1] | None = None,
        *,
        global_denied_commands: list[str] | None = None,
    ) -> None:
        self._bindings = bindings or []
        self._global_denied = set(global_denied_commands or [
            "rm -rf /",
            "mkfs",
            "dd if=/dev/zero",
            ":(){ :|:& };:",
        ])

    def evaluate(self, request: ExecRequest) -> ExecApprovalResult:
        """Evaluate an exec request against all bindings."""
        # Global deny check
        cmd_str = request.command.strip()
        for denied in self._global_denied:
            if cmd_str.startswith(denied):
                return ExecApprovalResult(
                    decision=ApprovalDecision.DENY,
                    reason=f"Globally denied: {denied}",
                )

        # Check timeout
        for binding in self._bindings:
            if request.timeout_ms > binding.max_timeout_ms:
                return ExecApprovalResult(
                    decision=ApprovalDecision.DENY,
                    reason=f"Timeout {request.timeout_ms}ms exceeds max {binding.max_timeout_ms}ms",
                )

        # Evaluate through bindings
        for binding in self._bindings:
            decision = binding.evaluate(request.argv, cwd=request.cwd)
            if decision != ApprovalDecision.PROMPT:
                # Filter env
                sanitized = {
                    k: v for k, v in request.env.items()
                    if binding.is_env_key_allowed(k)
                }
                return ExecApprovalResult(
                    decision=decision,
                    sanitized_env=sanitized,
                )

        # Default: prompt
        return ExecApprovalResult(
            decision=ApprovalDecision.PROMPT,
            reason="No binding matched; requires approval",
        )
