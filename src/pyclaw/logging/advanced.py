"""Advanced logging — file rotation, identifier redaction, diagnostic state, log parsing.

Ported from ``src/logging/*.ts``.

Provides:
- Log file rotation with size limits
- Identifier redaction (emails, IPs, phone numbers, API keys)
- Diagnostic session state logging
- Log line parsing (timestamp, level, subsystem, message)
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# File Rotation
# ---------------------------------------------------------------------------


@dataclass
class RotationConfig:
    """Configuration for log file rotation."""

    max_size_bytes: int = 10 * 1024 * 1024  # 10 MB
    max_files: int = 5
    compress: bool = False
    log_dir: str = ""


@dataclass
class RotationResult:
    """Result of a rotation check."""

    rotated: bool = False
    files_removed: int = 0
    current_size: int = 0


def should_rotate(log_path: str | Path, config: RotationConfig) -> bool:
    """Check if a log file needs rotation."""
    p = Path(log_path)
    if not p.exists():
        return False
    return p.stat().st_size >= config.max_size_bytes


def rotate_log_file(log_path: str | Path, config: RotationConfig) -> RotationResult:
    """Rotate a log file by renaming with timestamp suffix."""
    p = Path(log_path)
    if not p.exists():
        return RotationResult()

    size = p.stat().st_size
    if size < config.max_size_bytes:
        return RotationResult(current_size=size)

    timestamp = int(time.time())
    rotated_name = f"{p.stem}.{timestamp}{p.suffix}"
    rotated_path = p.parent / rotated_name
    p.rename(rotated_path)

    # Prune old rotated files
    pattern = f"{p.stem}.*{p.suffix}"
    rotated_files = sorted(p.parent.glob(pattern), key=lambda f: f.stat().st_mtime)
    files_removed = 0
    while len(rotated_files) > config.max_files:
        oldest = rotated_files.pop(0)
        oldest.unlink()
        files_removed += 1

    return RotationResult(rotated=True, files_removed=files_removed, current_size=0)


# ---------------------------------------------------------------------------
# Identifier Redaction
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_IP_RE = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
_PHONE_RE = re.compile(r"\+?\d[\d\s\-]{8,15}\d")
_API_KEY_RE = re.compile(r"(sk-[a-zA-Z0-9]{10,}|sk-ant-[a-zA-Z0-9]{10,}|gsk_[a-zA-Z0-9]{10,}|hf_[a-zA-Z0-9]{10,})")

REDACTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (_API_KEY_RE, "[REDACTED_KEY]"),
    (_EMAIL_RE, "[REDACTED_EMAIL]"),
    (_IP_RE, "[REDACTED_IP]"),
    (_PHONE_RE, "[REDACTED_PHONE]"),
]


def redact_identifiers(text: str) -> str:
    """Redact sensitive identifiers from text."""
    result = text
    for pattern, replacement in REDACTION_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def redact_api_key(key: str) -> str:
    """Mask an API key, showing only prefix and last 4 chars."""
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"


# ---------------------------------------------------------------------------
# Diagnostic Session State
# ---------------------------------------------------------------------------


@dataclass
class DiagnosticSessionState:
    """Capture diagnostic state for a session."""

    session_id: str
    agent_id: str = ""
    model: str = ""
    turn_count: int = 0
    tool_call_count: int = 0
    token_usage: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    started_at: float = 0.0
    last_activity_at: float = 0.0

    def to_log_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "model": self.model,
            "turns": self.turn_count,
            "tool_calls": self.tool_call_count,
            "tokens": self.token_usage,
            "errors": len(self.errors),
            "uptime_s": (self.last_activity_at - self.started_at) if self.started_at else 0,
        }


# ---------------------------------------------------------------------------
# Log Line Parsing
# ---------------------------------------------------------------------------


@dataclass
class ParsedLogLine:
    """A parsed log line."""

    timestamp: str = ""
    level: str = ""
    subsystem: str = ""
    message: str = ""
    raw: str = ""

    @property
    def is_error(self) -> bool:
        return self.level.upper() in ("ERROR", "CRITICAL")


_LOG_LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[.\d]*)\s+"
    r"(\w+)\s+"
    r"(?:\[([^\]]+)\]\s+)?"
    r"(.*)$"
)


def parse_log_line(line: str) -> ParsedLogLine:
    """Parse a structured log line into components."""
    m = _LOG_LINE_RE.match(line.strip())
    if not m:
        return ParsedLogLine(raw=line.strip(), message=line.strip())

    return ParsedLogLine(
        timestamp=m.group(1),
        level=m.group(2),
        subsystem=m.group(3) or "",
        message=m.group(4),
        raw=line.strip(),
    )


def filter_log_lines(
    lines: list[str],
    *,
    level: str = "",
    subsystem: str = "",
    pattern: str = "",
) -> list[ParsedLogLine]:
    """Filter and parse log lines."""
    results: list[ParsedLogLine] = []
    compiled = re.compile(pattern, re.IGNORECASE) if pattern else None

    for line in lines:
        parsed = parse_log_line(line)
        if level and parsed.level.upper() != level.upper():
            continue
        if subsystem and parsed.subsystem != subsystem:
            continue
        if compiled and not compiled.search(parsed.message):
            continue
        results.append(parsed)

    return results
