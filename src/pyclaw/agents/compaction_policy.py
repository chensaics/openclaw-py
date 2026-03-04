"""Compaction policy — identifier preservation, deduplication, and tool-name pruning.

Ported from ``src/agents/`` compaction logic.

Enhances session compaction with:
- Identifier preservation (keep system prompts, tool definitions, key anchors)
- Anti-duplicate compaction (detect near-duplicate assistant messages)
- Tool-name pruning (remove tool_use blocks for tools no longer available)
- Configurable retention policies per message role
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class RetentionPolicy(str, Enum):
    KEEP = "keep"  # Never compact
    COMPACT = "compact"  # Can be summarized
    PRUNE = "prune"  # Can be removed entirely


@dataclass
class CompactionConfig:
    """Configuration for session compaction."""

    max_tokens: int = 100000
    target_tokens: int = 80000
    preserve_system: bool = True
    preserve_last_n_turns: int = 4
    dedup_threshold: float = 0.85
    prune_unavailable_tools: bool = True
    role_policies: dict[str, RetentionPolicy] = field(
        default_factory=lambda: {
            "system": RetentionPolicy.KEEP,
            "user": RetentionPolicy.COMPACT,
            "assistant": RetentionPolicy.COMPACT,
            "tool": RetentionPolicy.COMPACT,
        }
    )


@dataclass
class CompactionCandidate:
    """A message evaluated for compaction."""

    index: int
    role: str
    content: str
    token_estimate: int = 0
    policy: RetentionPolicy = RetentionPolicy.COMPACT
    is_duplicate: bool = False
    content_hash: str = ""
    is_identifier: bool = False


@dataclass
class CompactionResult:
    """Result of compaction planning."""

    keep_indices: list[int]
    prune_indices: list[int]
    compact_indices: list[int]
    tokens_saved_estimate: int = 0
    duplicates_found: int = 0


def estimate_tokens(text: str) -> int:
    """Rough token estimate (chars / 4)."""
    return max(1, len(text) // 4)


def content_hash(text: str) -> str:
    """Compute a short hash for deduplication."""
    normalized = " ".join(text.lower().split())
    return hashlib.md5(normalized.encode()).hexdigest()[:12]


def is_identifier_message(content: str, *, role: str = "") -> bool:
    """Check if a message is an identifier/anchor that should be preserved.

    Identifiers include system prompts, tool definitions, and messages
    with explicit anchoring markers.
    """
    if role == "system":
        return True

    lower = content.lower()

    # Tool definitions
    if "function" in lower and "parameters" in lower and '"type"' in lower:
        return True

    # Anchoring markers
    anchors = ["[system]", "[anchor]", "[identity]", "you are", "your name is"]
    return any(a in lower for a in anchors)


def detect_near_duplicates(
    messages: list[dict[str, Any]],
    *,
    threshold: float = 0.85,
) -> list[tuple[int, int]]:
    """Detect near-duplicate message pairs by content similarity.

    Uses a simple normalized-hash approach — exact duplicates after
    whitespace normalization.  Returns pairs of (earlier_idx, later_idx)
    where later_idx is the duplicate.
    """
    seen: dict[str, int] = {}
    duplicates: list[tuple[int, int]] = []

    for i, msg in enumerate(messages):
        content = msg.get("content", "")
        if not content or not isinstance(content, str):
            continue

        h = content_hash(content)
        if h in seen:
            duplicates.append((seen[h], i))
        else:
            seen[h] = i

    return duplicates


def filter_unavailable_tools(
    messages: list[dict[str, Any]],
    available_tools: set[str],
) -> list[dict[str, Any]]:
    """Remove tool_use/tool_result blocks for tools no longer available.

    Keeps messages intact but strips tool-call/result pairs for
    pruned tools so the context doesn't reference phantom tools.
    """
    if not available_tools:
        return messages

    pruned_call_ids: set[str] = set()
    result: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role", "")

        # Check assistant tool_use blocks
        if role == "assistant":
            content = msg.get("content")
            if isinstance(content, list):
                filtered_blocks: list[Any] = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_name = block.get("name", "")
                        if tool_name and tool_name not in available_tools:
                            tool_id = block.get("id", "")
                            if tool_id:
                                pruned_call_ids.add(tool_id)
                            continue
                    filtered_blocks.append(block)

                if filtered_blocks:
                    result.append({**msg, "content": filtered_blocks})
                continue

        # Check tool results referencing pruned calls
        if role == "tool":
            tool_use_id = msg.get("tool_use_id", "")
            if tool_use_id in pruned_call_ids:
                continue

        result.append(msg)

    return result


def plan_compaction(
    messages: list[dict[str, Any]],
    *,
    config: CompactionConfig | None = None,
    available_tools: set[str] | None = None,
) -> CompactionResult:
    """Plan which messages to keep, compact, or prune.

    Does not modify messages — returns indices for the caller to act on.
    """
    cfg = config or CompactionConfig()

    # Build candidates
    candidates: list[CompactionCandidate] = []
    total_tokens = 0

    for i, msg in enumerate(messages):
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            content = str(content)

        tokens = estimate_tokens(content)
        total_tokens += tokens

        policy = cfg.role_policies.get(role, RetentionPolicy.COMPACT)
        is_id = is_identifier_message(content, role=role)

        if is_id and cfg.preserve_system:
            policy = RetentionPolicy.KEEP

        candidates.append(
            CompactionCandidate(
                index=i,
                role=role,
                content=content,
                token_estimate=tokens,
                policy=policy,
                content_hash=content_hash(content),
                is_identifier=is_id,
            )
        )

    # Detect duplicates
    duplicates = detect_near_duplicates(messages, threshold=cfg.dedup_threshold)
    dup_indices = {later for _, later in duplicates}
    for c in candidates:
        if c.index in dup_indices:
            c.is_duplicate = True
            c.policy = RetentionPolicy.PRUNE

    # Protect last N turns
    protected = set(range(max(0, len(candidates) - cfg.preserve_last_n_turns * 2), len(candidates)))

    # Classify
    keep: list[int] = []
    prune: list[int] = []
    compact: list[int] = []
    tokens_saved = 0

    for c in candidates:
        if c.index in protected or c.policy == RetentionPolicy.KEEP:
            keep.append(c.index)
        elif c.policy == RetentionPolicy.PRUNE or c.is_duplicate:
            prune.append(c.index)
            tokens_saved += c.token_estimate
        else:
            compact.append(c.index)

    return CompactionResult(
        keep_indices=keep,
        prune_indices=prune,
        compact_indices=compact,
        tokens_saved_estimate=tokens_saved,
        duplicates_found=len(duplicates),
    )
