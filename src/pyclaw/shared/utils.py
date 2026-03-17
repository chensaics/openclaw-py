"""Shared utilities — reasoning tags, frontmatter, API key masking, safe JSON, etc.

Ported from ``src/shared/`` and ``src/utils/``.

Provides:
- Reasoning tag extraction/stripping
- Code region detection
- Frontmatter parsing
- Usage aggregation
- API key masking
- Safe JSON parsing
- Timeout wrapper
- Concurrency control
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any, TypeVar

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Reasoning Tags
# ---------------------------------------------------------------------------

_REASONING_RE = re.compile(r"<(thinking|reasoning|reflection)>(.*?)</\1>", re.DOTALL)


def extract_reasoning(text: str) -> list[str]:
    """Extract content from reasoning/thinking tags."""
    return [m.group(2).strip() for m in _REASONING_RE.finditer(text)]


def strip_reasoning(text: str) -> str:
    """Remove reasoning/thinking tags from text."""
    return _REASONING_RE.sub("", text).strip()


def has_reasoning_tags(text: str) -> bool:
    return bool(_REASONING_RE.search(text))


# ---------------------------------------------------------------------------
# Code Regions
# ---------------------------------------------------------------------------

_CODE_FENCE_RE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)


@dataclass
class CodeRegion:
    """A detected code region."""

    language: str
    code: str
    start_pos: int
    end_pos: int


def find_code_regions(text: str) -> list[CodeRegion]:
    """Find all fenced code regions in text."""
    regions: list[CodeRegion] = []
    for m in _CODE_FENCE_RE.finditer(text):
        regions.append(
            CodeRegion(
                language=m.group(1) or "",
                code=m.group(2),
                start_pos=m.start(),
                end_pos=m.end(),
            )
        )
    return regions


def is_inside_code_block(text: str, position: int) -> bool:
    """Check if a position is inside a code fence."""
    return any(region.start_pos <= position <= region.end_pos for region in find_code_regions(text))


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse YAML-like frontmatter from text.

    Returns (frontmatter_dict, body_without_frontmatter).
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text

    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip()

    body = text[m.end() :]
    return fm, body


# ---------------------------------------------------------------------------
# API Key Masking
# ---------------------------------------------------------------------------


def mask_api_key(key: str, *, visible_chars: int = 4) -> str:
    """Mask an API key, showing only the last N chars."""
    if not key:
        return ""
    if len(key) <= visible_chars:
        return "****"
    return "*" * (len(key) - visible_chars) + key[-visible_chars:]


# ---------------------------------------------------------------------------
# Safe JSON
# ---------------------------------------------------------------------------


def safe_json_parse(text: str, default: Any = None) -> Any:
    """Parse JSON without raising exceptions."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_json_dumps(obj: Any, **kwargs: Any) -> str:
    """Serialize to JSON without raising exceptions."""
    try:
        return json.dumps(obj, **kwargs)
    except (TypeError, ValueError):
        return "{}"


# ---------------------------------------------------------------------------
# Timeout Wrapper
# ---------------------------------------------------------------------------


async def with_timeout(
    coro: Coroutine[Any, Any, T],
    timeout_s: float,
    *,
    default: T | None = None,
) -> T | None:
    """Run a coroutine with a timeout, returning default on timeout."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_s)
    except (TimeoutError, asyncio.TimeoutError):
        return default


# ---------------------------------------------------------------------------
# Concurrency Control
# ---------------------------------------------------------------------------


async def run_with_concurrency(
    tasks: list[Coroutine[Any, Any, T]],
    *,
    max_concurrent: int = 5,
) -> list[T | Exception]:
    """Run coroutines with bounded concurrency."""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def sem_task(coro: Coroutine[Any, Any, T]) -> T | Exception:
        async with semaphore:
            try:
                return await coro
            except Exception as e:
                return e

    gathered = await asyncio.gather(*(sem_task(t) for t in tasks))
    return list(gathered)


# ---------------------------------------------------------------------------
# Usage Aggregation
# ---------------------------------------------------------------------------


@dataclass
class UsageEntry:
    """A single usage entry."""

    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    timestamp: float = 0.0


def aggregate_usage(entries: list[UsageEntry]) -> dict[str, Any]:
    """Aggregate usage entries by model."""
    by_model: dict[str, dict[str, Any]] = {}
    for e in entries:
        if e.model not in by_model:
            by_model[e.model] = {"input_tokens": 0, "output_tokens": 0, "cost": 0.0, "count": 0}
        by_model[e.model]["input_tokens"] += e.input_tokens
        by_model[e.model]["output_tokens"] += e.output_tokens
        by_model[e.model]["cost"] += e.cost
        by_model[e.model]["count"] += 1

    return {
        "by_model": by_model,
        "total_input": sum(e.input_tokens for e in entries),
        "total_output": sum(e.output_tokens for e in entries),
        "total_cost": sum(e.cost for e in entries),
    }
