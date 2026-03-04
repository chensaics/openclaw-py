"""Exec hardening — obfuscation detection, wrapper resolution, approval forwarding.

Ported from ``src/infra/exec-approvals*.ts`` and ``src/security/obfuscation*.ts``.

Provides:
- Command obfuscation detection (base64, hex, eval wrappers)
- Shell wrapper resolution (env, nohup, timeout, nice, etc.)
- Approval forwarding for elevated commands
- Safe binary path policy
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ObfuscationResult:
    """Result of obfuscation detection."""

    is_obfuscated: bool
    signals: list[str] = field(default_factory=list)
    risk_score: float = 0.0  # 0.0 - 1.0
    decoded_hint: str = ""


# Patterns commonly used for obfuscation
_BASE64_CMD_RE = re.compile(
    r"(?:echo|printf)\s+['\"]?[A-Za-z0-9+/=]{10,}['\"]?\s*\|\s*(?:base64\s+-d|openssl\s+base64)"
)
_HEX_CMD_RE = re.compile(r"\\x[0-9a-fA-F]{2}(?:\\x[0-9a-fA-F]{2}){4,}")
_EVAL_RE = re.compile(r"\beval\s+(?:\$\(|`)")
_PYTHON_EXEC_RE = re.compile(r"python[23]?\s+-c\s+['\"].*(?:exec|eval|compile)\s*\(")
_PERL_EXEC_RE = re.compile(r"perl\s+-e\s+['\"].*eval")
_CURL_PIPE_RE = re.compile(r"curl\s+.*\|\s*(?:sh|bash|zsh|python)")
_WGET_PIPE_RE = re.compile(r"wget\s+.*-O\s*-\s*\|\s*(?:sh|bash|zsh)")

OBFUSCATION_PATTERNS: list[tuple[re.Pattern[str], str, float]] = [
    (_BASE64_CMD_RE, "base64-encoded command", 0.8),
    (_HEX_CMD_RE, "hex-encoded content", 0.7),
    (_EVAL_RE, "eval with command substitution", 0.9),
    (_PYTHON_EXEC_RE, "python exec/eval", 0.6),
    (_PERL_EXEC_RE, "perl eval", 0.6),
    (_CURL_PIPE_RE, "curl piped to shell", 0.9),
    (_WGET_PIPE_RE, "wget piped to shell", 0.9),
]


def detect_obfuscation(command: str) -> ObfuscationResult:
    """Detect common command obfuscation patterns."""
    signals: list[str] = []
    max_score = 0.0

    for pattern, label, score in OBFUSCATION_PATTERNS:
        if pattern.search(command):
            signals.append(label)
            max_score = max(max_score, score)

    return ObfuscationResult(
        is_obfuscated=bool(signals),
        signals=signals,
        risk_score=max_score,
    )


# ---------------------------------------------------------------------------
# Shell Wrapper Resolution
# ---------------------------------------------------------------------------

WRAPPER_COMMANDS = frozenset(
    {
        "env",
        "nohup",
        "timeout",
        "nice",
        "ionice",
        "strace",
        "ltrace",
        "time",
        "sudo",
        "doas",
        "unbuffer",
        "script",
        "setsid",
    }
)


def resolve_wrappers(argv: list[str]) -> list[str]:
    """Strip common shell wrappers to find the actual command."""
    i = 0
    while i < len(argv):
        cmd = Path(argv[i]).name
        if cmd in WRAPPER_COMMANDS:
            i += 1
            # Skip flags for wrapper commands
            while i < len(argv) and argv[i].startswith("-"):
                i += 1
        else:
            break
    return argv[i:]


def extract_base_command(command_line: str) -> str:
    """Extract the base command from a command line (strip wrappers, pipes, redirects)."""
    parts = command_line.split("|")[0].strip().split()
    if not parts:
        return ""
    resolved = resolve_wrappers(parts)
    if not resolved:
        return parts[0] if parts else ""
    return Path(resolved[0]).name


# ---------------------------------------------------------------------------
# Safe Binary Policy
# ---------------------------------------------------------------------------


@dataclass
class BinaryPolicy:
    """Policy for safe/allowed binaries."""

    allowed_paths: list[str] = field(
        default_factory=lambda: [
            "/usr/bin",
            "/usr/local/bin",
            "/bin",
            "/usr/sbin",
        ]
    )
    blocked_binaries: list[str] = field(
        default_factory=lambda: [
            "rm",
            "mkfs",
            "dd",
            "fdisk",
            "shutdown",
            "reboot",
            "halt",
            "init",
            "poweroff",
        ]
    )
    require_absolute: bool = False


def validate_binary(binary: str, policy: BinaryPolicy) -> tuple[bool, str]:
    """Validate a binary against the safety policy."""
    base_name = Path(binary).name

    if base_name in policy.blocked_binaries:
        return False, f"Blocked binary: {base_name}"

    if policy.require_absolute and not Path(binary).is_absolute():
        resolved = shutil.which(binary)
        if not resolved:
            return False, f"Binary not found: {binary}"

        in_allowed = any(resolved.startswith(p) for p in policy.allowed_paths)
        if not in_allowed:
            return False, f"Binary not in allowed paths: {resolved}"

    return True, ""


# ---------------------------------------------------------------------------
# Approval Forwarding
# ---------------------------------------------------------------------------


@dataclass
class ApprovalRequest:
    """A command approval request."""

    request_id: str
    command: str
    argv: list[str] = field(default_factory=list)
    obfuscation: ObfuscationResult | None = None
    base_command: str = ""
    requires_approval: bool = False
    reason: str = ""


def build_approval_request(
    request_id: str,
    command: str,
    *,
    policy: BinaryPolicy | None = None,
) -> ApprovalRequest:
    """Build an approval request for a command, performing all checks."""
    policy = policy or BinaryPolicy()
    argv = command.split()
    base_cmd = extract_base_command(command)
    obfuscation = detect_obfuscation(command)

    requires = False
    reason = ""

    if obfuscation.is_obfuscated:
        requires = True
        reason = f"Obfuscated command: {', '.join(obfuscation.signals)}"
    else:
        valid, msg = validate_binary(base_cmd, policy)
        if not valid:
            requires = True
            reason = msg

    return ApprovalRequest(
        request_id=request_id,
        command=command,
        argv=argv,
        obfuscation=obfuscation,
        base_command=base_cmd,
        requires_approval=requires,
        reason=reason,
    )
