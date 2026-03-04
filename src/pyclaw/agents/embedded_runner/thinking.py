"""Thinking + extensions — thinking block handling, context pruning, compaction safety.

Ported from ``src/agents/pi-embedded-runner/thinking.ts`` and ``extensions.ts``.

Provides:
- Thinking block extraction and processing
- Extended thinking mode management (enabled/disabled/budget)
- Context pruning extension (remove low-value content)
- Compaction safety guard (prevent data loss during compaction)
- Abort detection
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ThinkingMode(str, Enum):
    DISABLED = "disabled"
    ENABLED = "enabled"
    LOW = "low"
    HIGH = "high"


@dataclass
class ThinkingConfig:
    """Configuration for thinking/reasoning."""

    mode: ThinkingMode = ThinkingMode.DISABLED
    budget_tokens: int = 10000
    strip_from_output: bool = False
    log_thinking: bool = False


@dataclass
class ThinkingBlock:
    """A thinking/reasoning block from the LLM response."""

    content: str
    token_count: int = 0
    position: int = 0  # index in response

    @property
    def is_empty(self) -> bool:
        return not self.content.strip()


# Patterns for different providers' thinking formats
_THINKING_TAG_RE = re.compile(r"<thinking>(.*?)</thinking>", re.DOTALL)
_REASONING_TAG_RE = re.compile(r"<reasoning>(.*?)</reasoning>", re.DOTALL)
_REFLECTION_TAG_RE = re.compile(r"<reflection>(.*?)</reflection>", re.DOTALL)

# Anthropic extended thinking uses a content block with type "thinking"
_THINKING_PATTERNS = [_THINKING_TAG_RE, _REASONING_TAG_RE, _REFLECTION_TAG_RE]


def extract_thinking_blocks(text: str) -> list[ThinkingBlock]:
    """Extract thinking blocks from LLM output text."""
    blocks: list[ThinkingBlock] = []
    for pattern in _THINKING_PATTERNS:
        for match in pattern.finditer(text):
            blocks.append(
                ThinkingBlock(
                    content=match.group(1).strip(),
                    position=match.start(),
                )
            )
    return blocks


def strip_thinking_tags(text: str) -> str:
    """Remove thinking/reasoning/reflection tags from text."""
    result = text
    for pattern in _THINKING_PATTERNS:
        result = pattern.sub("", result)
    return result.strip()


def process_thinking_response(
    response_text: str,
    config: ThinkingConfig,
) -> tuple[str, list[ThinkingBlock]]:
    """Process an LLM response, extracting thinking blocks.

    Returns (cleaned_text, thinking_blocks).
    """
    blocks = extract_thinking_blocks(response_text)

    if config.log_thinking:
        for block in blocks:
            logger.debug("Thinking: %s", block.content[:200])

    if config.strip_from_output:
        cleaned = strip_thinking_tags(response_text)
        return cleaned, blocks

    return response_text, blocks


def build_thinking_param(config: ThinkingConfig) -> dict[str, Any] | None:
    """Build the thinking parameter for API requests (Anthropic format)."""
    if config.mode == ThinkingMode.DISABLED:
        return None

    return {
        "type": "enabled",
        "budget_tokens": config.budget_tokens,
    }


def parse_thinking_content_block(block: dict[str, Any]) -> ThinkingBlock | None:
    """Parse an Anthropic-style thinking content block."""
    if block.get("type") != "thinking":
        return None
    return ThinkingBlock(
        content=block.get("thinking", ""),
        token_count=0,
    )


# ---------------------------------------------------------------------------
# Context Pruning Extension
# ---------------------------------------------------------------------------


@dataclass
class PruningConfig:
    """Configuration for context pruning."""

    max_messages: int = 100
    max_tool_result_chars: int = 10000
    prune_empty_tool_results: bool = True
    prune_duplicate_content: bool = True


def prune_context(
    messages: list[dict[str, Any]],
    config: PruningConfig,
) -> tuple[list[dict[str, Any]], int]:
    """Prune low-value content from conversation context.

    Returns (pruned_messages, items_removed).
    """
    removed = 0
    result: list[dict[str, Any]] = []
    seen_contents: set[str] = set()

    for msg in messages:
        # Always keep system messages
        if msg.get("role") == "system":
            result.append(msg)
            continue

        content = msg.get("content", "")

        # Prune empty tool results
        if config.prune_empty_tool_results and msg.get("role") == "tool":
            if not content or content.strip() == "":
                removed += 1
                continue

        # Truncate overly long tool results
        if msg.get("role") == "tool" and isinstance(content, str):
            if len(content) > config.max_tool_result_chars:
                msg = {**msg, "content": content[: config.max_tool_result_chars] + "\n...(truncated)"}

        # Deduplicate identical content
        if config.prune_duplicate_content and isinstance(content, str):
            content_hash = content[:500]
            if content_hash in seen_contents and msg.get("role") == "assistant":
                removed += 1
                continue
            seen_contents.add(content_hash)

        result.append(msg)

    # Enforce max messages (keep system + most recent)
    if len(result) > config.max_messages:
        system_msgs = [m for m in result if m.get("role") == "system"]
        non_system = [m for m in result if m.get("role") != "system"]
        keep = config.max_messages - len(system_msgs)
        removed += len(non_system) - keep
        result = system_msgs + non_system[-keep:]

    return result, removed


# ---------------------------------------------------------------------------
# Compaction Safety Guard
# ---------------------------------------------------------------------------


@dataclass
class CompactionGuardConfig:
    """Configuration for compaction safety."""

    min_messages_after: int = 4
    protect_tool_pairs: bool = True
    max_compaction_ratio: float = 0.5


def is_compaction_safe(
    messages: list[dict[str, Any]],
    proposed_count: int,
    config: CompactionGuardConfig,
) -> tuple[bool, str]:
    """Check if a proposed compaction is safe."""
    if proposed_count < config.min_messages_after:
        return False, f"Would leave only {proposed_count} messages (min: {config.min_messages_after})"

    ratio = proposed_count / max(len(messages), 1)
    if ratio < config.max_compaction_ratio:
        return False, f"Compaction ratio {ratio:.2f} is too aggressive (max: {config.max_compaction_ratio})"

    if config.protect_tool_pairs:
        # Ensure tool_use messages have matching tool_result
        tool_call_ids = set()
        tool_result_ids = set()
        for msg in messages[-proposed_count:]:
            for tc in msg.get("tool_calls", []):
                tool_call_ids.add(tc.get("id", ""))
            if msg.get("tool_call_id"):
                tool_result_ids.add(msg["tool_call_id"])

        orphaned = tool_call_ids - tool_result_ids
        if orphaned:
            return False, f"Would orphan {len(orphaned)} tool call(s)"

    return True, ""


# ---------------------------------------------------------------------------
# Abort Detection
# ---------------------------------------------------------------------------


class AbortSignal:
    """Simple abort signal for embedded runs."""

    def __init__(self) -> None:
        self._aborted = False
        self._reason = ""
        self._aborted_at: float = 0.0

    def abort(self, reason: str = "user_abort") -> None:
        self._aborted = True
        self._reason = reason
        self._aborted_at = time.time()

    @property
    def is_aborted(self) -> bool:
        return self._aborted

    @property
    def reason(self) -> str:
        return self._reason

    def reset(self) -> None:
        self._aborted = False
        self._reason = ""
        self._aborted_at = 0.0
