"""Sensitive data redaction for logs and tool output.

Ported from ``src/logging/redact.ts``.
Patterns cover API keys, tokens, PEM blocks, and common credential formats.
"""

from __future__ import annotations

import re
from typing import Any, Literal

RedactMode = Literal["off", "tools"]

# Token prefix patterns that should be redacted
_TOKEN_PREFIXES = [
    r"sk-[a-zA-Z0-9]{20,}",
    r"sk-proj-[a-zA-Z0-9_-]{20,}",
    r"sk-ant-[a-zA-Z0-9_-]{20,}",
    r"ghp_[a-zA-Z0-9]{20,}",
    r"gho_[a-zA-Z0-9]{20,}",
    r"github_pat_[a-zA-Z0-9_]{20,}",
    r"xoxb-[a-zA-Z0-9\-]{20,}",
    r"xoxp-[a-zA-Z0-9\-]{20,}",
    r"xapp-[a-zA-Z0-9\-]{20,}",
    r"AIza[a-zA-Z0-9_-]{30,}",
    r"glpat-[a-zA-Z0-9_-]{20,}",
    r"npm_[a-zA-Z0-9]{20,}",
    r"pypi-[a-zA-Z0-9]{20,}",
    r"AKIA[A-Z0-9]{16}",
    r"eyJ[a-zA-Z0-9_-]{40,}",  # JWT
]

_TOKEN_RE = re.compile("|".join(f"({p})" for p in _TOKEN_PREFIXES))

# PEM block redaction
_PEM_RE = re.compile(
    r"-----BEGIN [A-Z ]+-----[\s\S]*?-----END [A-Z ]+-----",
    re.MULTILINE,
)

# Environment variable assignment patterns
_ENV_RE = re.compile(
    r"(?:^|\s)([A-Z_][A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|AUTH)[A-Z0-9_]*)=(\S+)",
    re.IGNORECASE,
)

# JSON field redaction (keys containing sensitive words)
_JSON_FIELD_RE = re.compile(
    r'"((?:api[_-]?key|token|secret|password|credential|auth[_-]?token|access[_-]?token|bearer)[^"]*?)"\s*:\s*"([^"]+)"',
    re.IGNORECASE,
)

# Authorization headers
_AUTH_HEADER_RE = re.compile(
    r"(Authorization|Bearer|X-API-Key)\s*[:=]\s*(\S+)",
    re.IGNORECASE,
)

# Custom patterns from config
_custom_patterns: list[re.Pattern[str]] = []


def set_custom_redact_patterns(patterns: list[str]) -> None:
    """Set custom regex patterns to redact."""
    global _custom_patterns
    _custom_patterns = []
    for p in patterns:
        try:
            _custom_patterns.append(re.compile(p))
        except re.error:
            pass


def redact_sensitive_text(text: str) -> str:
    """Redact known sensitive patterns from *text*."""
    result = _TOKEN_RE.sub("[REDACTED]", text)
    result = _PEM_RE.sub("[REDACTED PEM BLOCK]", result)
    result = _ENV_RE.sub(lambda m: f"{m.group(1)}=[REDACTED]", result)
    result = _JSON_FIELD_RE.sub(lambda m: f'"{m.group(1)}": "[REDACTED]"', result)
    result = _AUTH_HEADER_RE.sub(lambda m: f"{m.group(1)}: [REDACTED]", result)
    for pat in _custom_patterns:
        result = pat.sub("[REDACTED]", result)
    return result


def redact_tool_detail(tool_name: str, detail: str, mode: RedactMode = "tools") -> str:
    """Redact sensitive data from tool output.

    Only redacts when *mode* is ``"tools"``; ``"off"`` returns unmodified text.
    """
    if mode == "off":
        return detail
    return redact_sensitive_text(detail)
