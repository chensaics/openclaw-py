"""Tool guards — allowlist, context guard, result truncation, schema splitting, cache TTL.

Ported from ``src/agents/pi-embedded-runner/tool-*.ts`` and ``cache-ttl.ts``.

Provides:
- Tool allowlist filtering
- Context guard (prevent tools from leaking sensitive context)
- Tool result truncation for token budget
- Schema splitting for providers with schema limits
- Provider-specific cache TTL management
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool Allowlist
# ---------------------------------------------------------------------------

@dataclass
class AllowlistConfig:
    """Configuration for tool allowlist."""
    mode: str = "all"  # "all" | "allowlist" | "blocklist"
    allowed_tools: list[str] = field(default_factory=list)
    blocked_tools: list[str] = field(default_factory=list)
    always_allowed: list[str] = field(default_factory=lambda: [
        "computer", "bash", "text_editor",
    ])


def filter_tools(
    tools: list[dict[str, Any]],
    config: AllowlistConfig,
) -> list[dict[str, Any]]:
    """Filter tools based on allowlist/blocklist configuration."""
    if config.mode == "all":
        result = [t for t in tools if t.get("function", {}).get("name") not in config.blocked_tools]
        return result

    if config.mode == "blocklist":
        return [
            t for t in tools
            if t.get("function", {}).get("name") not in config.blocked_tools
        ]

    if config.mode == "allowlist":
        allowed = set(config.allowed_tools) | set(config.always_allowed)
        return [
            t for t in tools
            if t.get("function", {}).get("name") in allowed
        ]

    return tools


# ---------------------------------------------------------------------------
# Context Guard
# ---------------------------------------------------------------------------

SENSITIVE_PATTERNS = frozenset({
    "api_key", "secret", "password", "token", "credential",
    "private_key", "access_key", "auth",
})


def guard_tool_context(
    tool_name: str,
    args: dict[str, Any],
    *,
    redact_sensitive: bool = True,
) -> dict[str, Any]:
    """Guard tool arguments, redacting sensitive values."""
    if not redact_sensitive:
        return args

    guarded = {}
    for key, value in args.items():
        if any(p in key.lower() for p in SENSITIVE_PATTERNS):
            guarded[key] = "[REDACTED]"
        elif isinstance(value, str) and len(value) > 10000:
            guarded[key] = value[:10000] + "...(truncated)"
        else:
            guarded[key] = value

    return guarded


# ---------------------------------------------------------------------------
# Result Truncation
# ---------------------------------------------------------------------------

@dataclass
class TruncationConfig:
    """Configuration for tool result truncation."""
    max_result_chars: int = 50000
    max_result_lines: int = 500
    truncation_marker: str = "\n...(result truncated)"
    preserve_json_structure: bool = True


def truncate_tool_result(
    result: str,
    config: TruncationConfig | None = None,
) -> str:
    """Truncate a tool result to fit within limits."""
    config = config or TruncationConfig()

    if len(result) <= config.max_result_chars:
        lines = result.split("\n")
        if len(lines) <= config.max_result_lines:
            return result
        return "\n".join(lines[:config.max_result_lines]) + config.truncation_marker

    # Try to preserve JSON structure
    if config.preserve_json_structure and result.strip().startswith("{"):
        try:
            parsed = json.loads(result)
            compact = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
            if len(compact) <= config.max_result_chars:
                return compact
        except json.JSONDecodeError:
            pass

    return result[:config.max_result_chars] + config.truncation_marker


# ---------------------------------------------------------------------------
# Schema Splitting
# ---------------------------------------------------------------------------

@dataclass
class SchemaSplitConfig:
    """Configuration for schema splitting."""
    max_tools_per_request: int = 128
    max_schema_bytes: int = 200000


def should_split_schema(
    tools: list[dict[str, Any]],
    config: SchemaSplitConfig,
) -> bool:
    """Check if tools should be split across multiple requests."""
    if len(tools) > config.max_tools_per_request:
        return True

    total_bytes = sum(len(json.dumps(t)) for t in tools)
    if total_bytes > config.max_schema_bytes:
        return True

    return False


def split_schema(
    tools: list[dict[str, Any]],
    config: SchemaSplitConfig,
) -> list[list[dict[str, Any]]]:
    """Split tools into chunks that fit within limits."""
    if not should_split_schema(tools, config):
        return [tools]

    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_bytes = 0

    for tool in tools:
        tool_bytes = len(json.dumps(tool))
        if (
            len(current) >= config.max_tools_per_request
            or current_bytes + tool_bytes > config.max_schema_bytes
        ):
            if current:
                chunks.append(current)
            current = [tool]
            current_bytes = tool_bytes
        else:
            current.append(tool)
            current_bytes += tool_bytes

    if current:
        chunks.append(current)

    return chunks


# ---------------------------------------------------------------------------
# Cache TTL
# ---------------------------------------------------------------------------

@dataclass
class CacheEntry:
    """A cached value with TTL."""
    key: str
    value: Any
    created_at: float
    ttl_s: float

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_s


# Default TTLs per provider (seconds)
PROVIDER_CACHE_TTLS: dict[str, float] = {
    "openai": 300.0,
    "anthropic": 300.0,
    "google": 180.0,
    "groq": 60.0,
    "together": 120.0,
    "fireworks": 120.0,
    "deepseek": 300.0,
    "ollama": 0.0,  # No caching for local
}


class ToolCacheManager:
    """Manage cached tool results with provider-specific TTLs."""

    def __init__(self) -> None:
        self._cache: dict[str, CacheEntry] = {}

    def get(self, key: str) -> Any | None:
        entry = self._cache.get(key)
        if not entry:
            return None
        if entry.is_expired:
            self._cache.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: Any, *, ttl_s: float = 300.0) -> None:
        self._cache[key] = CacheEntry(
            key=key, value=value, created_at=time.time(), ttl_s=ttl_s,
        )

    def compute_key(self, tool_name: str, args: dict[str, Any]) -> str:
        """Compute a cache key from tool name and arguments."""
        content = json.dumps({"tool": tool_name, "args": args}, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def get_ttl(self, provider: str) -> float:
        return PROVIDER_CACHE_TTLS.get(provider, 300.0)

    def cleanup_expired(self) -> int:
        expired = [k for k, v in self._cache.items() if v.is_expired]
        for k in expired:
            self._cache.pop(k, None)
        return len(expired)

    @property
    def size(self) -> int:
        return len(self._cache)
